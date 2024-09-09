
class Cache{
};

class SimpleCache:public Cache{
    class CPUSidePort{
        char* blockedPacket = nullptr;
        void sendPacketResp(char* pkt = nullptr, int len = 12 *76);
        bool sendTimingResp(char* pkt){
            return false;
        }
    };
    SimpleCache(){}
};

int calc(int a, int b){
    return a + b;
}

void
SimpleCache::CPUSidePort::sendPacketResp(char* pkt, int len)
{
    int apple = (len << 1) + (*blockedPacket);
    if (!calc(len + apple, apple)) {
        blockedPacket = pkt;
    } else if (len > 1){
        blockedPacket = nullptr;
    }
}