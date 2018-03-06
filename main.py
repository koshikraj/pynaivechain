from sanic import Sanic
from sanic.response import json

sockets = []

QUERY_LATEST = 0
QUERY_ALL = 1
RESPONSE_BLOCKCHAIN = 2

http_port = 3001
p2p_port = 6001
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

@app.route('/blocks')
async def blocks(request):
    return json(blockchain)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=http_port)
