# -*- coding: utf-8 -*-
# 使用一个散列来存储登录cookie令牌与已登录用户之间的映射。
# 检查令牌，在登录的情况下返回用户id
import json
import time


def check_token(conn, token):
    return conn.hget('login:', token)
# 更新令牌
# 每次浏览页面都会对用户存在登陆散列里边的信息进行更新，并将用户的令牌和当前时间戳添加到记录
# 最近登录用户的有序集合里，如果用户正在浏览的是一个商品页面，会将这个商品添加到记录这个用户
# 最近浏览过的商品的有序集合里，并在被记录的商品超过25个时，对这个有序集合进行修剪。


def update_token(conn, token, user, item=None):
    timestamp = time.time()
    # hset key field value
    conn.hset('login:', token, user)
    # zadd(key, member, score)：向名称为key的zset中
    # 添加元素member，score用于排序。如果该元素已经存在，则根据score更新该元素的顺序。
    conn.zadd('recent:', token, timestamp)
    if item:
        conn.zadd('viewed:' + token, item, timestamp)
        # zremrangebyrank(key, min, max)：删除名称为key的zset中rank >= min
        # 且rank <= max的所有元素,下边这种0，-26代表保留最近的25条数据
        conn.zremrangebyrank('viewed:' + token, 0, -26)
# 在服务端保留1000W个会话，清理会话的程序有一个循环构成，每次执行的时候检查存储最近登录
# 令牌的有序集合的大小，
# 超限移除最多100个最旧的令牌，并从记录用户信息的散列中删除被删除的用户信息，并对存储了
# 这些用户最近浏览商品记录的有序集合进行清理。
# 没超限，休眠1s
# 网络上每秒能清理1W多个令牌，能够妥善的处理每天500W的访问
# 这会导致一个问题：有一个race condition，假如清理函数正在删除用户信息，同时用户访问网站
# 会导致用户的信息被错误的删除，使得用户需要重新登录一次，后边会搞懂怎么办。


QUIT = False
LIMIT = 10000000


def clean_sessions(conn):
    while not QUIT:
        # zcard key 返回key中元素个数
        size = conn.zcard('recent:')
        if size < LIMIT:
            time.sleep(1)
            continue
        end_index = min(size - LIMIT, 100)
        # 获取需要移除的令牌id
        tokens = conn.zrange('recent:', 0, end_index-1)

        session_keys = []
        for token in tokens:
            session_keys.append('viewed:' + token)
            session_keys.append('cart:' + token)
        # 移除旧令牌相关的数据
        conn.delete(*session_keys)
        conn.hdel('login:', *tokens)
        conn.zrem('recent:', *tokens)

# 使用redis实现购物车,除了可以减少请求的体积，还是得我们可以根据用户浏览过的商品、用户放入购物车的
# 商品以及用户最终购买的商品进行统计计算，用于商业分析。


def add_to_cart(conn, session, item, count):
    if count < 0:
        conn.hrem('cart:' + session, item)
    else:
        conn.hset('cart:' + session, item, count)

# 网页缓存
# 创建一个中间件来调用redis缓存函数，对于可以被缓存的请求，函数先尝试从缓存中取出并返回被缓存的页面
# 如果缓存页面不存在，函数会生成页面并将其在redis中缓存5分钟，最后再将页面返回给函数调用者
# 包含大量数据的页面网络延迟一般为20-50ms，缓存到redis中可以将其降低至查询一次redis所需的时间5ms左右


def can_cache(conn, request):
    pass


def hash_request(request):
    return str(hash(request))


def cache_request(conn, request, callback):
    if not can_cache(conn, request):
        return callback(request)
    page_key = 'cache:' + hash_request(request)
    content = conn.get(page_key)

    if not content:
        content = callback(request)
        conn.setex(page_key, content, 300)
    return content

# 如何搞一次促销？
# 编写一个持续运行的守护进程函数，让这个函数将指定的数据行缓存到redis中，不定期的对缓存进行更新
# 缓存函数会将数据行编码为JSON字典并存储在redis的字符串里，数据列的名字(column)被映射为json字
# 典的key，数据行的值会被映射为json字典的value
# ----inv:273---------------string-
# {
#  "qty":629,"name":"GTab 7inch","description":"..."
# }
# 使用了两个有序集合来记录应该在何时对缓存进行更新: 第一个有序集合为调度(schedule)有序集合，他的
# 成员为数据行的行ID，分值是一个时间戳，这个时间戳记录了应该在何时将指定的数据行缓存到redis中，第
# 二个有序集合为(delay)延迟有序集合，他的成员也是数据行的id，分值记录了指定数据行的缓存需要每隔多
# 久更新一次，<=0说明不需要再缓存该行数据。


def schedule_row_cache(conn, row_id, delay):
    # 先设置数据行的延迟值
    conn.zadd('delay:', row_id, delay)
    # 立即对需要缓存的数据行进行调度
    conn.zadd('schedule:', row_id, time.time())

# 缓存函数，先尝试读取调度有序集合的第一个元素以及分值，如果调度有序集合为空，或者分值存储的时间戳尚未来临
# 函数会先休眠50ms，然后重新检查。当发现一个需要立即进行更新的数据行时，缓存函数会检查这个数据行的延迟值：
# 如果数据行的延迟值<=0，那么从延迟和调度有序集合中移除该数据行的id，从缓存中删除这个数据行已有的缓存，然后
# 重新检查对于延迟值>=0的数据行，缓存函数从数据库取出这些行，并将它们编码为JSON存储到redis中，然后更新这
# 些行的调度时间


class Inventory:
    def get(self, _id):
        """
        从数据库中按id获取信息
        """
        return 'data'


def cache_rows(conn):
    while not QUIT:
        # 获取下一个需要被缓存的数据行以及该行的调度时间戳，命令会返回一个
        # 包含0个或一个元组的列表。[(row_id, timestamp)]
        next = conn.zrange('schedule:', 0, 0, withscores=True)
        now = time.time()
        if not next or next[0][1] > now:
            time.sleep(.05)
            continue
        row_id = next[0][0]
        # zscore(key, element)：返回名称为key的zset中元素element的score
        delay = conn.zscore('delay:', row_id)
        if delay <= 0:
            # 删除该行的所有缓存
            conn.zrem('delay:', row_id)
            conn.zrem('schedule:', row_id)
            conn.delete('inv:' + row_id)
            continue
        row = Inventory.get(row_id)
        conn.zadd('schedule:', row_id, now + delay)
        conn.set('inv:' + row_id, json.dumps(row.to_dict()))


# 只缓存一部分页面来减少实现页面缓存所需的内存数量
# 网站可以从用户的访问、交互和购买行为中收集到有价值的信息，但是假如网站包含10W件商品上边的策略会
# 将缓存所有的页面，调研后决定只对其中1W件商品页面进行缓存。
# 每个用户都有一个相应的记录用户浏览商品历史的有序集合，尽管使用这些有序集合可以计算出用户经常浏览
# 的商品，但进行这种计算却需要大量的时间，为了解决这个问题，再update_token中添加一行代码


def update_token(conn, token, user, item=None):
    timestamp = time.time()
    conn.hset('login:', token, user)
    conn.zadd('recent:', token, timestamp)

    if item:
        conn.zadd('viewed:' + token, item, timestamp)
        conn.zremrangebyrank('viewed:' + token, 0, -26)
        # zincrby(key, increment, member) ：如果在名称为key的zset中已经存在元素member，则
        # 该元素的score增加increment；否则向集合中添加该元素，其score的值为increment
        # 新建了一个viewed的zset，浏览的最多的商品在索引0上，并且具有整个集合的最小分值。
        conn.zincrby('viewed:', item, -1)

# 程序还要发现那些变得越来越流行的新商品
# 为了能让商品浏览次数排行榜保持最新，需要定期修剪有序集合的长度并调整已有元素的分值，从而使得新的
# 流行商品也可以在排行榜里占据一席之地，移除可以用zremrangebyrank,而调整元素可以用zinterstore可以
# 求一个或多个集合的交集，并将有序集合包含的每个分值都乘以一个给定的数值（可以给每个有序集合指定不同的
# 值相乘）。
# 每隔五分钟rescale_viewed会删除所有排名在20000之后的商品，并将删除后剩余的所有商品的浏览次数减半


def rescale_viewed(conn):
    while not QUIT:
        conn.zremrangebyrank('viewed:', 0, -20001)
        #
        conn.zinterstore('viewed:', {'viewed:': .5})
        time.sleep(300)


def extract_item_id(request):return 'id'


def is_dynamic(request):pass


def can_cache(conn, request):
    # 尝试从页面里取出商品id
    item_id = extract_item_id(request)
    # 检查页面是否能被缓存，以及是否为商品页面
    if not item_id or is_dynamic(request):
        return False
    # 取得商品的浏览次数排名
    rank = conn.zrank('viewed:', item_id)
    # 根据商品的浏览次数排名来判断是否需要缓存这个页面
    return rank is not None and rank < 10000

# 如果想用更少的代价存储更多的页面，可以先对页面进行压缩，然后在缓存到redis中，或者
# 使用edge side includes技术移除页面中的部分内容，或者对模板进行提前优化，移除所有
# 非必要的空格字符，这些技术能够减少内存消耗并增加redis能够缓存的页面数。
