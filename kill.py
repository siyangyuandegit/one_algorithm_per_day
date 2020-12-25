# -*- coding: utf-8 -*-
# @Time    : 2020/12/24 3:41 下午
# @Author  : lbb
# @FileName: kill.py
# @Software: PyCharm
"""
有100个人站成一圈，贴上1到100的标签。第一个人拿到一把刀，kill站在他旁边的人，然后交给下一个活着的人。也就是说，一号会kill
二号，把刀交给三号。第三个人会遵循和第一个人一样的行为，这个过程一直持续下去，直到圈子里的所有人都被kill，只剩下一个人。那这个人的标签是多少?

"""
# 列表用时22.720415830612183s链表用时0.01096544075012207s
# 以上数据测试了10000个数据的用时
import time
# start = time.time()
# peoples = [i for i in range(1, 10000)]
# count = len(peoples)
# qq = 0
# while count > 1:
#     if count == 2:
#         peoples.remove(peoples[1])
#         count -= 1
#         break
#     for index, people in enumerate(peoples):
#         if index & 1 != 0:
#             peoples[index] = 'killed'
#             print(peoples)
#             qq += 1
#         if index == count - 2 and peoples[index] == 'killed':
#             peoples[0] = 'killed'
#             print('倒数第二个人被kill需要kill掉第一个人', peoples)
#             qq += 1
#     print('kill ', qq)
#     count -= qq
#     for i in range(qq):
#         peoples.remove('killed')
#     qq = 0
#     print('remain :', peoples)
# print('列表用时', time.time() - start)
# print('最终活下来的是：', peoples[0])

######
"""
我jio的可以用链表做
"""


class Node:
    def __init__(self):
        self.val = None
        self.next = None


class ListNode:
    def __init__(self):
        self.head = None
        self.tail = None
        self.length = 0

    # 尾插
    def add_to_tail(self, val):
        node = Node()
        node.val = val
        # 如果是个空链表，头尾节点指向该节点，随后更新尾节点
        if not self.head:
            self.head = node
            self.tail = node
        # 如果不是空链表,让之前的尾节点指向该节点，更新尾节点
        else:
            self.tail.next = node
            self.tail = node
        self.length += 1

    # 头插
    def add_to_head(self, val):
        node = Node()
        node.val = val
        # 如果是空链表，头尾头节点指向该节点，随后更新头节点
        if not self.head:
            self.tail, self.head = node, node
        # 如果不是空链表，该节点指向头节点，头节点更新为该节点
        else:
            node.next, self.head = self.head, node
        self.length += 1

    # 打印链表
    def print_listnode(self):
        cur = self.head
        while cur:
            print(cur.val)
            cur = cur.next

    # 成环
    def create_circle(self):
        self.tail.next = self.head

    # 反转链表
    def reverse(self):
        cur, prev = self.head, None
        self.tail = self.head
        while cur:
            cur.next, prev, cur = prev, cur, cur.next
        self.head = prev
        return prev
# # 测试链表
# a = ListNode()
# for i in range(1, 101):
#     a.add_to_head(i)
# p = a.head
# while p.next:
#     print(p.val)
#     p = p.next
# print(p.val)
# print(a.length)


# # 链表的实现
start = time.time()
peoples = ListNode()
for i in range(1, 10):
    # peoples.add_to_tail(i)
    peoples.add_to_head(i)
peoples.reverse()
peoples.print_listnode()
print('尾节点：',peoples.tail.val)
print('头节点：',peoples.head.val)
# 生成环形链表
# peoples.create_circle()
# 然后从头节点开始指向下下个节点。
# cur = peoples.head
# # while peoples.length > 1:
# while cur.next and cur.next is not cur: # 这里使用这种判断方式比计算长度要快0.002秒左右提升约17%
#     cur.next, cur = cur.next.next, cur.next.next
#     # peoples.length -= 1
# print(cur.val)
# print('链表用时', time.time() - start)
