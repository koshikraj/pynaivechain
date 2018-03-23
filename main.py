import json as JSON
import os
import websockets

from Crypto.Hash import SHA256
from datetime import datetime
from sanic import Sanic
from sanic.response import json
from websockets.exceptions import ConnectionClosed

sockets = []

QUERY_LATEST = 0
QUERY_ALL = 1
RESPONSE_BLOCKCHAIN = 2

try:
    port = int(os.environ['PORT'])
except Exception as e:
    port = 3001

try:
    initialPeers = os.environ['PEERS'].split(",")
except Exception as e:
    initialPeers = []

class Block(object):

    def __init__(self, index, previousHash, timestamp, data, hash):
        self.index = index
        self.previousHash = previousHash
        self.timestamp = timestamp
        self.data = data
        self.hash = hash

def getGenesisBlock():

    # SHA256.new(data=(str(0) + "0"+ str(1465154705) +"my genesis block!!").encode()).hexdigest()

    return Block(0, "0", 1465154705, "my genesis block!!", "816534932c2b7154836da6afc367695e6337db8a921823784c14378abed4f7d7")


blockchain = [getGenesisBlock()]


app = Sanic()


@app.route('/blocks', methods=['GET'])
async def blocks(request):
    return json(blockchain)

@app.route('/mineBlock', methods=['POST'])
async def mine_block(request):

    try:
        newBlock = generateNextBlock(request.json["data"])
    except KeyError as e:
        return json({"status": False, "message": "pass value in data key"})
    addBlock(newBlock)
    await broadcast(responseLatestMsg())
    return json(newBlock)

@app.route('/peers', methods=['GET'])
async def blocks(request):
    peers = map(lambda x: "{}:{}".format(x.remote_address[0], x.remote_address[1])
                , sockets)
    return json(peers)

@app.route('/addPeer', methods=['POST'])
async def blocks(request):
    import asyncio
    asyncio.ensure_future(connectToPeers([request.json["peer"]]),
                                         loop=asyncio.get_event_loop())
    return json({"status": True})

async def connectToPeers(newPeers):
    for peer in newPeers:
        print(peer)
        try:
            ws = await websockets.connect(peer)

            await initConnection(ws)
        except Exception as e:
            print(str(e))

# initP2PServer WebSocket server
@app.websocket('/')
async def feed(request, ws):
    print('listening websocket p2p port on: %d' % port);


    try:
        await initConnection(ws)
    except (ConnectionClosed):
        await closeConnection(ws)


async def closeConnection(ws):
    print("connection failed to peer")
    sockets.remove(ws)

async def initConnection(ws):

    print("inside initConnection")

    sockets.append(ws)
    print(dir(ws))
    await ws.send(JSON.dumps(queryChainLengthMsg()))

    while True:
        await initMessageHandler(ws)


async def initMessageHandler(ws):
    data = await ws.recv()
    message = JSON.loads(data)
    print('Received message', data)

    await {
        QUERY_LATEST: sendLatestMsg,
        QUERY_ALL: sendChainMsg,
        RESPONSE_BLOCKCHAIN: handleBlockchainResponse
    }[message["type"]](ws, message)

async def sendLatestMsg(ws, *args):
    await ws.send(JSON.dumps(responseLatestMsg()))

async def sendChainMsg(ws, *args):

    await ws.send(JSON.dumps(responseChainMsg()))



def generateNextBlock(blockData):
    previousBlock = getLatestBlock()
    nextIndex = previousBlock.index + 1
    nextTimestamp = datetime.now().strftime("%s")
    nextHash = calculateHash(nextIndex, previousBlock.hash, nextTimestamp, blockData)
    return Block(nextIndex, previousBlock.hash, nextTimestamp, blockData, nextHash)

def getLatestBlock():
    try:
        return blockchain[-1]
    except IndexError as e:
        return None

def responseChainMsg():

    return {
    'type': RESPONSE_BLOCKCHAIN,
    'data': JSON.dumps([formatBlock(block) for block in blockchain])
    }

def responseLatestMsg():

    return {
    'type': RESPONSE_BLOCKCHAIN,
    'data': JSON.dumps([formatBlock(getLatestBlock())])
    }

# Unable to serialize the block object without formatting it
def formatBlock(block):

    return {"data": block.data,
            "hash": block.hash,
            "index": block.index,
            "previousHash": block.previousHash,
            "timestamp": block.timestamp}

def calculateHashForBlock(block):

    return calculateHash(block.index, block.previousHash, block.timestamp, block.data)

def calculateHash(index, previousHash, timestamp, data):

    hash_object = SHA256.new(data=(str(index) + previousHash + str(timestamp) + data).encode())
    return hash_object.hexdigest()

def addBlock(newBlock):

    if (isValidNewBlock(newBlock, getLatestBlock())):
        blockchain.append(newBlock)

def isValidNewBlock(newBlock, previousBlock):

    if (previousBlock.index + 1 != newBlock.index):
        print('invalid index')
        return False
    elif (previousBlock.hash != newBlock.previousHash):
        print('invalid previoushash');
        return False
    elif (calculateHashForBlock(newBlock) != newBlock.hash):
      print( type(newBlock.hash) + ' ' + type(calculateHashForBlock(newBlock)))
      print('invalid hash: ' + calculateHashForBlock(newBlock) + ' ' + newBlock.hash)
      return False

    return True

async def handleBlockchainResponse(ws, message):

    receivedBlocks = sorted(JSON.loads(message["data"]), key=lambda k: k['index'])
    print (receivedBlocks)
    latestBlockReceived = receivedBlocks[-1];
    latestBlockHeld = getLatestBlock();
    if (latestBlockReceived["index"] > latestBlockHeld.index):
        print('blockchain possibly behind. We got: ' + str(latestBlockHeld.index) + ' Peer got: ' + str(latestBlockReceived["index"]))
        if (latestBlockHeld.hash == latestBlockReceived["previousHash"]):
            print("We can append the received block to our chain")

            blockchain.append(Block(**latestBlockReceived))
            await broadcast(responseLatestMsg())
        elif (len(receivedBlocks) == 1):
            print("We have to query the chain from our peer")
            await broadcast(queryAllMsg())
        else:
            print("Received blockchain is longer than current blockchain")
            await replaceChain(receivedBlocks)
    else:
        print('received blockchain is not longer than current blockchain. Do nothing')

async def replaceChain(newBlocks):

    global blockchain
    try:

        if isValidChain(newBlocks) and len(newBlocks) > len(blockchain):
            print('Received blockchain is valid. Replacing current blockchain with '
                  'received blockchain')
            blockchain = [Block(**block) for block in newBlocks]
            await broadcast(responseLatestMsg())
        else:
            print('Received blockchain invalid')
    except Exception as e:
        print ("error in replace" + str(e))

def isValidChain(blockchainToValidate):

    if calculateHashForBlock(Block(**blockchainToValidate[0])) != getGenesisBlock().hash:
        return False

    tempBlocks = [Block(**blockchainToValidate[0])]
    for currentBlock in blockchainToValidate[1:]:
        if(isValidNewBlock(Block(**currentBlock), tempBlocks[-1])):
            tempBlocks.append(Block(**currentBlock))
        else:
            return False
    return True

def queryChainLengthMsg():

    return {'type': QUERY_LATEST}

def queryAllMsg():

    return {'type': QUERY_ALL}

async def broadcast(message):

    for socket in sockets:
        print (socket)
        await socket.send(JSON.dumps(message))

if __name__ == '__main__':

    app.add_task(connectToPeers(initialPeers))
    app.run(host='0.0.0.0', port=port, debug=True)
