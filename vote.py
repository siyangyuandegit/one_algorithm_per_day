# -*- coding: utf-8 -*-
import time

ONE_WEEK_IN_SECONDS = 7 * 86400
# 这个数字是每天200票一共86400s，每票对应432秒，把这个东西作为一个分值，加到时间戳里
# 这样就实现了一个随着时间流逝而不断减少的分值
VOTE_SCORE = 432

# 每页显示的文章
ARTICLES_PRE_PAGE = 25

# 假如一篇文章获得了至少200票，就认为它是有趣的，假如这个网站每天发布1000篇文章，而其中的50篇符合网站对有趣文章的要求，那么网站要做的就是把这50篇文章放在文章列表的前100位至少一天
# 为了产生一个能够随着时间流逝而不断减少的评分，程序需要根据文章的发布时间和当前时间来计算文章的评分，具体方法为：将文章得到的支持票数量乘以一个常量，然后加上文章的发布时间，
# 使用hash来存储文章的标题，指向文章的网址等信息
# ----article: 102928----------------hash---
# ------------------------------------------
# title | Go to statement considered harmful
# link  | http://goo.gl/kZUsu
# poster | user:87362
# time  | 13331313131.22
# votes | 578
# 根据发布时间排序文章的有序集合
# -----time--------------------zset----
# -------------------------------------
# article: 10298 | 13131333330.33
# article: 10238 | 13131333331.33
# article: 10398 | 13131333333.33
# 根据评分排序文章的有序集合
# -----score------------------zset-----
# -------------------------------------
# article:100023 | 1332164063.38
# article:100022 | 1332164064.38
# article:100702 | 1332164065.38
# 为了防止用户对同一篇文章多次投票，为每篇文章记录一个已投票的用户名单
# 为了节约内存，规定一周后就不能对文章投票了，并且删除voted这个set
# ---voted: 10048-----------------set---
# --------------------------------------
# user:29298
# user:29292
# user:29291

# 文章点赞


def article_vote(conn, user, article):
    # time.time()返回的是秒为单位的时间戳
    cutoff = time.time() - ONE_WEEK_IN_SECONDS
    # zadd(key, score, member)：向名称为key的zset中添加元素member，score用于排序。
    # 如果该元素已经存在，则根据score更新该元素的顺序。
    # zscore(key, element)：返回名称为key的zset中元素element的score
    # 小于的话证明文章发布超过一周不能进行投票了
    # article ------->    article: 100029
    if conn.zscore('time:', article) < cutoff:
        return
    article_id = article.partition(':')[-1]
    # 如果用户第一次投票，给文章加分，把用户加入到voted中
    if conn.sadd('voted:' + article_id, user):
        conn.zincrby('score:', article, VOTE_SCORE)
        # hincrby key field increment 给某个field加指定的值
        conn.hincrby(article, 'votes', 1)


# 发布并获取文章
# 1、创建文章ID，可以通过对一个计数器执行incr来完成
# 2、用sadd将文章发布者ID添加到记录文章已投票用户名单的集合中，使用expire设置一周过期时间
# 3、使用HMSET存储文章其他相关信息
# 4、使用两个zadd，将文章的初始评分和发布时间分别添加到两个相应的有序集合中


def post_article(conn, user, title, link):
    # set 'article:' 100000     incr会返回100001
    article_id = str(conn.incr('article:'))

    voted = 'voted:' + article_id
    # 把作者id加到set voted: 中,设置一周的过期时间
    conn.sadd(voted, user)
    conn.expire(voted, ONE_WEEK_IN_SECONDS)

    now = time.time()
    article = 'article:' + article_id
    # 就是创建了article为key, 多个field，title,link等
    conn.hmset(article, {
        'title': title,
        'link': link,
        'poster': user,
        'time': now,
        'votes': 1,
    })
    # 添加两个zset，一个按发布时间，一个按评分
    # 初始有自己的投票，所以加一次分数
    conn.zadd('score:', article, now + VOTE_SCORE)
    conn.zadd('time:', article, now)
    return article_id


# 取出评分最高的文章，以及如何取出最新发布的文章
# 1、使用zrevrange取出多个文章id
# 有序集合会根据成员的分值从小到大地排列元素，所以使用zreverange，以分值从大到小取出
# zrevrange(key, start, end)：返回名称为key的zset（元素已按score从大到小排序）
# 中的index从start到end的所有元素
# 2、对每个文章id执行一次hgetall，取出详细信息
# hgetall key 获取key中所有的field，value


def get_articles(conn, page, order='score:'):
    # 获取文章的起始索引和结束索引
    start = (page-1) * ARTICLES_PRE_PAGE
    end = start + ARTICLES_PRE_PAGE - 1

    ids = conn.zrevrange(order, start, end)
    articles = []
    for _id in ids:
        article_data = conn.hgetall(_id)
        # 把文章ID存到文章信息中
        article_data['id'] = _id
        articles.append(article_data)
    return articles


# 对文章进行分组
# 这个功能可以让用户只看见与特定话题有关的文章，比如与"可爱的动物"有关的文章，
# 与"python"有关的文章。
# 群组功能由两个部分组成，一部分负责记录文章属于哪个群组，另一部分负责去除群组
# 中的文章，为了记录哥哥群组都保存了那些文章，需要为每个群组创建一个集合，并将所有
# 同属于一个群组的文章ID都记录到那个集合中。


def add_remove_groups(conn, article_id, to_add=[], to_remove=[]):
    """
    to_add：要把文章添加到那些群组
    to_remove: 要把文章从那些群组中移除
    """
    article = 'article:' + article_id
    # 将文章添加到对应的群组
    for group in to_add:
        conn.sadd('group:' + group, article)
    # 从群组中移除文章
    for group in to_remove:
        conn.srem('group:' + group, article)


# zinterstore 集合求交集
# 对存储群组文章的集合和存储文章发布时间的有序集合，获得按发布时间排序的群组文章。
# 如果群组文章很多zinterstore很耗时，将这个计算的结果缓存60s，重用get_articles()获取文章
# zincrby(key, increment, member) ：如果在名称为key的zset中已经存在元素member，
# 则该元素的score增加increment；否则向集合中添加该元素，其score的值为increment


def get_group_articles(conn, group, page, order='score:'):
    key = order + group
    if not conn.exists(key):
        # aggregate有三个参数max,min,sum
        conn.zinterstore(key,
                         ['group:' + group, order],
                         aggregate='max',
                         )
        conn.expire(key, 60)
    return get_articles(conn, page, key)