'''
The image cache is used to store copies of the image locally, so that we do not have
to fetch the image every time we wish to edit it. The cache implements a LRU policy.
Each entry is a key (channel id, message id).
'''
class ImgCache():
    def __init__(self, size):
        self.size = size
        self.cache = {}
        self.lru = None
        self.mru = None

    def get(self, key):
        if key in self.cache:
            cached = self.cache[key]
            self.__update_lru(cached)
            return cached.value

    def put(self, key, value):
        cached = None
        if key in self.cache:
            cached = self.cache[key]
            cached.value = value
        elif len(self.cache) < self.size:
            cached = ImageCacheEntry(key, value)
            self.cache[key] = cached
        else:
            #Evict a node to make space
            #print("EVICTED", self.lru.key)
            del self.cache[self.lru.key]
            self.lru = self.lru.next
            self.lru.prev = None

            cached = ImageCacheEntry(key, value)
            self.cache[key] = cached
        self.__update_lru(cached)

    def __update_lru(self, cached):
        #Update entries old neighbors
        if cached.next:
            cached.next.prev = cached.prev
            if cached == self.lru:
                self.lru = cached.next
        if cached.prev:
            cached.prev.next = cached.next

        #Make entry mru
        if self.mru:
            self.mru.next = cached
        cached.prev = self.mru
        self.mru = cached
        if not self.lru:
            self.lru = cached

class ImageCacheEntry():
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None