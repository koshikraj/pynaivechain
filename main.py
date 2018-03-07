from Crypto.Hash import SHA256

from datetime import datetime
from sanic import Sanic
from sanic.response import json
from websockets.exceptions import ConnectionClosed
import websockets


import json as JSON

sockets = []

QUERY_LATEST = 0
QUERY_ALL = 1
RESPONSE_BLOCKCHAIN = 2

http_port = 3005
p2p_port = 6001
initialPeers = ["ws://localhost:3007"]

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


@app.route('/blocks')
async def blocks(request):
    return json(blockchain)

@app.route('/mineBlock')
async def mine_block(request):
    newBlock = generateNextBlock("datatsdas")
    addBlock(newBlock)
    await broadcast(responseLatestMsg())
    return json(newBlock)

async def connectToPeers(newPeers):
    for peer in newPeers:
        print(peer)
        try:
            ws = await websockets.connect(peer)
            sockets.append(ws);
            await initConnection(ws)
        except Exception as e:
            print ("connect to p" + str(e))

# initP2PServer WebSocket server
@app.websocket('/')
async def feed(request, ws):
    print('listening websocket p2p port on: %d' % http_port);

    while True:
        try:
            await initConnection(ws)
        except (ConnectionClosed):
            await closeConnection(ws)
            break

async def closeConnection(ws):
    print("connection failed to peer")
    sockets.remove(ws)

async def initConnection(ws):

    await initMessageHandler(ws)
    # write(ws, queryChainLengthMsg())

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
            replaceChain(receivedBlocks)
    else:
        print('received blockchain is not longer than current blockchain. Do nothing')

async def replaceChain(newBlocks):

    if isValidChain(newBlocks) and len(newBlocks) > len(blockchain):
        print('Received blockchain is valid. Replacing current blockchain with '
              'received blockchain')
        blockchain = newBlocks
        await broadcast(responseLatestMsg())
    else:
        print('Received blockchain invalid')

def isValidChain(blockchainToValidate):

    if JSON.dumps(blockchainToValidate[0]) != JSON.dumps(getGenesisBlock()):
        return False
    tempBlocks = [blockchainToValidate[0]]
    for currentBlock in blockchainToValidate[1:]:
        if(isValidNewBlock(currentBlock, tempBlocks[-1])):
            tempBlocks.append(currentBlock)
        else:
            return False
    return True

def queryAllMsg():

    return {'type': QUERY_ALL}

async def broadcast(message):

    for socket in sockets:
        await socket.send(JSON.dumps(message))

if __name__ == '__main__':

    app.add_task(connectToPeers(initialPeers))
    app.run(host='0.0.0.0', port=http_port, debug=True)

