# 스택 · 큐 · 덱 정리 (보너스)

세 자료구조는 모두 "원소를 어느 쪽에 넣고 어느 쪽에서 꺼내는가"로 구분됩니다. 이 프로젝트에서는 별도 저장소 없이 **이중 연결 리스트를 감싼 어댑터**로 구현했습니다(`mini_redis/structures/stack_queue_deque.py`).

## 한눈에 비교

| | 스택 (Stack) | 큐 (Queue) | 덱 (Deque) |
| --- | --- | --- | --- |
| 원칙 | LIFO: 나중에 넣은 것이 먼저 | FIFO: 먼저 넣은 것이 먼저 | 양쪽 끝 모두 넣고 빼기 |
| 비유 | 접시 쌓기 | 매표소 줄 | 양쪽 문이 열린 통로 |
| 넣기 | `push` (top) | `enqueue` (rear) | `append`, `appendleft` |
| 빼기 | `pop` (top) | `dequeue` (front) | `pop`, `popleft` |
| 보기 | `peek` | `peek` | `peek_front`, `peek_back` |
| 시간 복잡도 | 모두 O(1) | 모두 O(1) | 모두 O(1) |

```
Stack      push → [ a | b | c ] → pop        (같은 쪽)
Queue   enqueue → [ a | b | c ] → dequeue    (반대쪽)
Deque  ⇄ [ a | b | c ] ⇄                     (양쪽 모두)
```

## 구현 방식별 장단점

| 구현 | 스택 | 큐 | 덱 |
| --- | --- | --- | --- |
| 동적 배열 (끝에서만 조작) | 좋음: 끝 push/pop 평균 O(1), 캐시 친화적 | 나쁨: 앞에서 빼면 원소를 당겨야 해서 O(n) | 나쁨: 앞쪽 조작 O(n) |
| 원형 배열 (head/tail 인덱스) | 가능 | 좋음: O(1), 메모리 연속 | 좋음: O(1), 가득 차면 확장 필요 |
| 이중 연결 리스트 | 가능: O(1) | 가능: O(1) | 좋음: 양 끝 O(1), 확장 비용 없음 |

이 프로젝트는 이미 검증한 이중 연결 리스트를 재사용해 세 구조를 각각 20줄 안팎으로 만들었습니다. 노드마다 포인터 2개가 붙는 메모리 비용은 있지만, 용량 확장 없이 모든 연산이 항상 O(1)이라는 장점이 있습니다.

## 프로젝트 내 활용처

| 구조 | 사용 위치 | 이유 |
| --- | --- | --- |
| Queue | `pubsub.py` — 구독자별 메시지 버퍼 (`Client.inbox`) | 발행된 순서대로 받아야 하므로 FIFO |
| Queue | `binary_tree.py` — 레벨 순회, `bst.py` — 높이 계산 | BFS는 가까운 노드부터 방문 = FIFO |
| Deque (maxlen) | `server.py` — 최근 명령어 `HISTORY` | 새 명령은 뒤에 넣고, 100개를 넘으면 가장 오래된 앞쪽을 버림 |
| Deque (maxlen) | `store.py` — 최근 LRU 제거 기록 `DEBUG EVICTIONS` | 제거할 때마다 (키, 크기, 시각)을 뒤에 넣고, 16개를 넘으면 가장 오래된 앞쪽을 버림 |
| Stack | `bst.py` — 중위 순회, 범위 조회 | 재귀 호출 스택을 직접 만든 스택으로 대체해 깊은 트리에서도 RecursionError 없음 |

## 실무와 Redis에서의 예

- **Redis List**는 양 끝 삽입/삭제(`LPUSH`, `RPUSH`, `LPOP`, `RPOP`)를 지원하는 덱입니다. `LPUSH + RPOP` 조합으로 작업 큐를, `LPUSH + LPOP`으로 스택을 만듭니다.
- **함수 호출 스택**, 괄호 짝 검사, 실행 취소(undo)는 스택입니다.
- **작업 큐**, 메시지 브로커, BFS, 프린터 대기열은 큐입니다.
- **슬라이딩 윈도우 최댓값**, 최근 N개 로그 보관은 덱입니다.

## 확인

```bash
python -m unittest tests.test_bonus_structures -v
python main.py < examples/05_bonus_pubsub.txt   # Queue(메시지 버퍼) + Deque(HISTORY)
```
