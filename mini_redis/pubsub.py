"""Pub/Sub (발행/구독) — 보너스 과제.

구조
* ``PubSub.channels``  : HashMap[채널명 -> DoublyLinkedList[Client]]  (채널별 구독자 목록)
* ``Client.subscriptions`` : HashMap[채널명 -> 구독자 리스트 안의 내 노드]
  → 구독 해제 시 채널 리스트를 탐색하지 않고 노드 핸들로 O(1) 제거 (LRU 와 같은 아이디어)
* ``Client.inbox``     : Queue[(채널, 메시지)]  (구독자별 메시지 버퍼, FIFO)

PUBLISH 는 채널의 구독자 리스트를 한 번 순회하며 각자의 inbox 에 메시지를 넣는다: O(구독자 수).

실제 Redis 는 네트워크 연결마다 클라이언트가 존재하지만, 이 프로젝트는 단일 REPL 이므로
``CLIENT SWITCH <name>`` 으로 "현재 클라이언트"를 바꿔가며 여러 구독자를 흉내 낸다.
"""

from typing import Tuple

from .structures.dynamic_array import DynamicArray
from .structures.hashmap import HashMap
from .structures.linked_list import DoublyLinkedList
from .structures.stack_queue_deque import Queue


class Client:
    """REPL 안에서 흉내 내는 접속 클라이언트."""

    __slots__ = ("name", "subscriptions", "inbox")

    def __init__(self, name: str) -> None:
        self.name = name
        self.subscriptions = HashMap()  # channel -> Node (채널 구독자 리스트 안의 내 노드)
        self.inbox = Queue()            # (channel, message) 버퍼

    def subscription_count(self) -> int:
        return self.subscriptions.size()

    def drain(self) -> DynamicArray:
        """쌓인 메시지를 모두 꺼낸다(FIFO)."""
        out = DynamicArray()
        while not self.inbox.is_empty():
            out.append(self.inbox.dequeue())
        return out


class PubSub:
    """채널별 구독자 목록을 관리하고 메시지를 각 구독자의 inbox 로 전달한다."""

    __slots__ = ("channels", "published")

    def __init__(self) -> None:
        self.channels = HashMap()  # channel -> DoublyLinkedList[Client]
        self.published = 0

    def subscribe(self, client: Client, channel: str) -> int:
        """구독 후 클라이언트의 총 구독 채널 수를 반환한다. 이미 구독 중이면 그대로."""
        if not client.subscriptions.contains(channel):
            subscribers = self.channels.get(channel)
            if subscribers is None:
                subscribers = DoublyLinkedList()
                self.channels.put(channel, subscribers)
            node = subscribers.insert_back(client)
            client.subscriptions.put(channel, node)
        return client.subscription_count()

    def unsubscribe(self, client: Client, channel: str) -> int:
        """구독 해제 후 남은 구독 채널 수를 반환한다."""
        node = client.subscriptions.get(channel)
        if node is not None:
            subscribers = self.channels.get(channel)
            subscribers.remove_node(node)        # O(1)
            client.subscriptions.remove(channel)
            if subscribers.is_empty():
                self.channels.remove(channel)
        return client.subscription_count()

    def subscribed_channels(self, client: Client) -> DynamicArray:
        return client.subscriptions.keys()

    def publish(self, channel: str, message: str) -> int:
        """채널 구독자 모두의 inbox 에 메시지를 넣고, 받은 구독자 수를 반환한다."""
        subscribers = self.channels.get(channel)
        if subscribers is None:
            return 0
        count = 0
        for client in subscribers:
            item: Tuple[str, str] = (channel, message)
            client.inbox.enqueue(item)
            count += 1
        self.published += 1
        return count

    def numsub(self, channel: str) -> int:
        subscribers = self.channels.get(channel)
        return 0 if subscribers is None else len(subscribers)
