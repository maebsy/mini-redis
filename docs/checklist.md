# 체크리스트 답변서

미션 체크리스트의 모든 항목에 대해 **충족 근거(코드·테스트·실행 방법)**와 **설명 답변**을 정리했습니다.
리뷰어가 질문할 때 이 문서의 해당 항목을 펼쳐 보면 바로 답할 수 있도록 구성했습니다.

> 표기: 📂 코드 위치 · 🧪 자동 테스트 · ▶️ 직접 확인 명령

- [항목 1. 기능 동작](#항목-1-기능-동작)
- [항목 2. 자료구조 구현](#항목-2-자료구조-구현)
- [항목 3. 동작 원리](#항목-3-동작-원리)
- [항목 4. 확장 질문](#항목-4-확장-질문)

---

## 항목 1. 기능 동작

### 1-1. String 타입 기본 동작: SET, GET, DEL, EXISTS, DBSIZE, KEYS ✅

- ▶️ `python main.py < examples/01_basic.txt`
- 🧪 `tests/test_server.py::StringCommandsTest`
- 📂 `mini_redis/server.py` `_cmd_set` ~ `_cmd_keys` → `mini_redis/store.py` `Store.set/get/delete/exists/dbsize/keys`

| 명령 | 결과 |
| --- | --- |
| `SET k v` | `OK` (성공 시 LRU 갱신, 기존 TTL 초기화) |
| `GET k` | `"v"` 또는 `(nil)` (성공 시에만 LRU 갱신) |
| `DEL k` | `(integer) 1` / `(integer) 0` (데이터·LRU·TTL에서 함께 제거) |
| `EXISTS k` | `(integer) 1` / `(integer) 0` |
| `DBSIZE` | `(integer) N` (만료 키 제외) |
| `KEYS` | `1) "k"` … / `(empty array)` |

### 1-2. LRU 자동 제거: maxmemory 초과 시 가장 오래된 키가 제거되는가 ✅

- ▶️ `python main.py < examples/02_lru.txt` (과제 결과 예시와 같은 흐름)
- 🧪 `tests/test_store.py::LruEvictionTest` (예시 재현, GET이 LRU를 갱신하는지, 여러 개 연속 제거, OOM), `EvictionLogTest` (제거 기록)
- ▶️ `DEBUG EVICTIONS` — 어떤 키가 언제 제거됐는지 최신순으로 확인 ([`design.md` 3.8](design.md#38-제거-기록-관찰-debug-evictions)), 여러 키 제거 순서 예시는 [`design.md` 3.3](design.md#config-set-maxmemory-축소와-여러-키-제거-순서)

```
CONFIG SET maxmemory 30
SET user:1 "Alice"     → used 11
SET user:2 "Bob"       → used 20
SET user:3 "Charlie"   → used 33 > 30 → LRU인 user:1 제거 → used 22, evicted_keys 1
GET user:1             → (nil)
```

### 1-3. INFO memory: used_memory / maxmemory / evicted_keys ✅

- 🧪 `tests/test_server.py::MemoryAndTtlCommandsTest::test_mission_example_transcript`
- 📂 `server.py::_cmd_info`

`used_memory = Σ(len(utf8(key)) + len(utf8(value)))` 공식을 그대로 적용하며 노드·버킷 등 자료구조 오버헤드는 제외합니다. 한글은 UTF-8로 한 글자 3바이트로 계산합니다(`test_entry_size_uses_utf8_bytes`).

### 1-4. TTL 관리: EXPIRE/TTL 규칙과 만료 키 제거 ✅

- ▶️ `python main.py < examples/03_ttl.txt`
- 🧪 `tests/test_store.py::TtlTest` (13개 케이스)

| 규칙 | 구현 | 테스트 |
| --- | --- | --- |
| 없는 키에 EXPIRE → `0` | `Store.expire` | `test_expire_missing_key_returns_false` |
| seconds ≤ 0 → 즉시 삭제, `1` | `Store.expire` | `test_non_positive_seconds_expire_immediately` |
| TTL: 없음 `-2`, 만료 없음 `-1`, 남은 초 `N` | `Store.ttl` | `test_ttl_codes` |
| 만료 키 GET → 삭제 후 `(nil)`, LRU 갱신 없음 | `Store._lookup`, `Store.get` | `test_expired_get_does_not_touch_lru` |
| SET 덮어쓰기 → TTL 초기화 | `Store.set` | `test_set_overwrite_clears_ttl` |
| DEL → 데이터/TTL/LRU 모두 제거 | `Store._remove_entry` + lazy deletion | `test_delete_then_reset_ignores_stale_heap_entry` |

### 1-5. 에러 처리: 잘못된 명령/인자/정수 오류/OOM이 표준 형식인가 ✅

- ▶️ `python main.py < examples/04_errors.txt`
- 🧪 `tests/test_server.py::ErrorFormatTest`

```
(error) ERR unknown command 'HELLO'
(error) ERR wrong number of arguments for 'GET' command
(error) ERR value is not an integer or out of range
(error) OOM command not allowed when used_memory > 'maxmemory'
```

---

## 항목 2. 자료구조 구현

### 2-1. 이중 연결 리스트의 노드 구조와 O(1) 메서드 구성 ✅

📂 `mini_redis/structures/linked_list.py` · 🧪 `tests/test_linked_list.py`

**답변.** 노드는 `prev`, `next`, `data` 세 필드만 가지며 `__slots__`로 고정했습니다(테스트로도 확인). 리스트 양 끝에는 데이터가 없는 **센티널 노드** `_head`, `_tail`을 둡니다. 실제 노드는 항상 두 센티널 사이에 있으므로 어떤 노드를 지우든 "앞 노드의 next를 뒤 노드로, 뒤 노드의 prev를 앞 노드로" 바꾸는 같은 코드(`_unlink`)로 끝납니다. 삽입도 `_link_after(anchor, node)` 하나로 앞/뒤 삽입을 모두 처리합니다.

모든 연산은 리스트 길이와 무관하게 포인터 2~4개만 바꾸므로 O(1)입니다. 단, `remove_node`/`move_to_front`가 O(1)이려면 **노드를 이미 알고 있어야** 합니다. 그래서 `insert_*`가 노드 객체를 반환하고, LRU는 그 노드를 `Entry.lru_node`에 보관합니다. 노드를 찾으려고 리스트를 순회하면 O(n)이 되기 때문에, "노드 핸들 보관"이 O(1)의 전제 조건입니다.

### 2-2. 해시 함수가 입력을 받아 인덱스를 만드는 과정 ✅

📂 `structures/hashmap.py::fnv1a_64`, `HashMap._index` · 🧪 `tests/test_hashmap.py::HashFunctionTest`

**답변.** FNV-1a 64비트를 직접 구현했습니다.

1. 키 문자열을 UTF-8 바이트로 바꿉니다. (`"user:1"` → 6바이트, 한글은 글자당 3바이트)
2. 해시값을 offset basis `0xCBF29CE484222325`로 시작합니다.
3. 바이트마다 `h ^= byte`로 섞고, `h *= 0x100000001B3`(FNV 소수)로 비트를 퍼뜨린 뒤 `& (2^64-1)`로 64비트를 유지합니다.
4. `h & (capacity - 1)`로 버킷 인덱스를 구합니다. capacity를 항상 2의 거듭제곱으로 유지하므로 나머지 연산 대신 비트 마스크를 쓸 수 있습니다.

XOR 후 곱하는 순서(1a 변형) 덕분에 마지막 글자만 다른 `user:1`, `user:2`도 해시값 전체가 달라집니다. 내장 `hash()`는 실행마다 시드가 바뀌어 재현이 안 되고 과제 요구사항이 "직접 설계"라서 사용하지 않았으며, AST 테스트(`test_hashmap_does_not_use_builtin_hash`)로 보장합니다. 공개 테스트 벡터(`fnv1a_64("a") == 0xAF63DC4C8601EC8C`)와 비교해 구현이 표준과 일치함을 확인했습니다.

### 2-3. 체이닝 충돌 해결 구현 (버킷 내부 구조 선택 포함) ✅

📂 `HashMap.put/get/remove/_find_node` · 🧪 `test_collisions_are_chained`

**답변.** 버킷 테이블은 `[None] * capacity` 고정 배열이고, 각 칸은 비어 있으면 `None`, 키가 있으면 `DoublyLinkedList`입니다. 같은 인덱스로 온 엔트리 `(key, value)`는 그 리스트 뒤에 붙습니다. 조회·삭제는 해당 버킷의 체인만 앞에서부터 비교합니다.

버킷 내부 구조로 이중 연결 리스트를 고른 이유는 (1) 과제 권장사항이고 (2) 이미 검증한 리스트를 재사용할 수 있으며 (3) 배열과 달리 중간 원소를 지울 때 뒤 원소를 당길 필요가 없기 때문입니다. 빈 버킷은 리스트를 만들지 않고(지연 생성), 마지막 원소가 빠지면 다시 `None`으로 돌려 메모리를 아낍니다.

테스트에서는 **모든 키를 같은 버킷으로 보내는 해시 함수**를 주입해 20개 키를 한 체인에 몰아넣고도 put/get/remove가 정확한지 확인합니다. `DEBUG HASHMAP`으로 실제 데이터의 최장 체인 길이를 볼 수 있습니다.

### 2-4. 로드 팩터 0.75 초과 시 버킷 2배 확장 절차 ✅

📂 `HashMap.put`, `HashMap._resize` · 🧪 `test_resize_when_load_factor_exceeds_075`

**답변.** `put`으로 새 키를 넣은 직후 `size / capacity > 0.75`를 검사합니다. 넘으면 `_resize(capacity * 2)`를 호출합니다.

1. 기존 버킷 테이블을 잠시 보관하고, 크기가 2배인 새 테이블을 만듭니다.
2. 기존 테이블의 모든 체인을 순회합니다.
3. 각 엔트리의 인덱스를 **새 capacity로 다시 계산**(`h & (new_capacity - 1)`)해서 새 테이블 체인에 붙입니다.

capacity가 8에서 16으로 바뀌면 인덱스 계산에 쓰는 비트가 3개에서 4개로 늘어나므로 위치가 바뀌는 키가 생깁니다. 그래서 복사가 아니라 재해싱이 필요합니다. 예를 들어 capacity 8에서 6개(0.75)까지는 확장하지 않고, 7번째(0.875)에서 16으로 확장됩니다. 확장 한 번은 O(n)이지만 2배씩 늘리므로 n번 삽입의 총 재배치 비용은 2n 미만이고, 한 번당 평균 O(1)입니다.

---

## 항목 3. 동작 원리

### 3-1. LRU에서 해시맵과 이중 연결 리스트의 역할, 둘 다 필요한 이유 ✅

**답변.** LRU 캐시는 두 가지 질문에 빨리 답해야 합니다.

| 질문 | 담당 | 혼자 쓰면 생기는 문제 |
| --- | --- | --- |
| "이 키가 있나? 어디 있나?" | 해시맵 (O(1) 조회) | 해시맵에는 순서가 없어, 가장 오래된 키를 찾으려면 전체를 훑어야 함 → O(n) |
| "가장 오래 안 쓴 키는? 방금 쓴 키를 맨 앞으로" | 이중 연결 리스트 (O(1) 이동/삭제) | 리스트만 있으면 특정 키를 찾는 데 순회가 필요 → O(n) |

해시맵의 값(`Entry`)이 리스트 노드를 가리키도록(`Entry.lru_node`) 연결하면 두 구조의 장점을 합칠 수 있습니다. 해시맵으로 노드를 즉시 찾고, 리스트에서 그 노드를 즉시 옮기거나 지웁니다. 단일 연결 리스트가 아니라 **이중** 연결 리스트인 이유는, 중간 노드를 지울 때 앞 노드(`prev`)를 O(1)로 알아야 하기 때문입니다.

### 3-2. O(1) LRU 달성 원리: "조회(해시) + 갱신(리스트 이동)" ✅

📂 `Store.get`, `Store.set`, `Store._evict_until_fits`

**답변.**

- **조회**: `HashMap.get(key)` → 평균 O(1)로 `Entry`를 얻습니다.
- **갱신**: `entry.lru_node`를 `move_to_front` → 포인터 6개 변경, O(1)
- **제거**: 리스트 맨 뒤 노드(`_lru.last`)가 곧 LRU 키 → `remove_node` O(1), 해시맵에서 삭제 O(1)

어느 단계에도 "전체 키를 훑는" 작업이 없으므로 GET/SET/제거가 모두 데이터 개수와 무관한 상수 시간입니다. 벤치마크에서 GET 처리량이 1천 건과 10만 건에서 비슷하게 유지되는 것으로 확인했습니다([`benchmark.md`](benchmark.md)).

### 3-3. TTL 관리에 힙을 쓴 이유 ✅

📂 `Store.expire_due_keys`, `structures/min_heap.py`

**답변.** 만료 처리에서 필요한 질문은 "지금 만료된 키가 있나?"입니다. 최소 힙은 **가장 이른 만료 시각을 루트에서 O(1)로** 보여줍니다.

- 루트가 아직 미래면 → 나머지도 전부 미래이므로 즉시 중단 (전체 키를 볼 필요 없음)
- 루트가 지났으면 → `pop`(O(log n))하고 다음 루트를 확인

만료된 키가 k개면 비용은 O(k log n)입니다. 비교 대상인 "모든 키를 순회하며 만료 확인"은 매번 O(n)이고, "만료 시각순 정렬 리스트"는 삽입이 O(n)입니다. 힙은 삽입 O(log n) + 최솟값 확인 O(1)이라 TTL에 가장 균형이 좋습니다.

힙 중간 원소 삭제는 위치를 찾는 데 O(n)이 들어서, DEL이나 TTL 초기화 때는 힙을 건드리지 않고 **꺼낼 때 검증**(lazy deletion)합니다. `entry is None` 또는 `entry.expire_at != 힙의 expire_at`이면 오래된 항목으로 보고 버립니다.

### 3-4. 메모리 초과 시 eviction 전체 흐름 ✅

📂 `Store.set`, `Store._evict_until_fits` · 🧪 `test_evicts_multiple_until_fits`, `ConsistencyTest`

**답변.**

1. **크기 산정**: `size = len(utf8(key)) + len(utf8(value))`
2. **단일 엔트리 검사**: `maxmemory > 0`이고 `size > maxmemory`면 저장하지 않고 OOM 에러. 기존 값도 그대로 둡니다.
3. **저장 + used_memory 갱신**: 새 키면 `+= size`, 덮어쓰기면 `+= size - 기존 size`. 이 키는 리스트 맨 앞(MRU)으로 갑니다.
4. **제거 루프**: `used_memory > maxmemory`인 동안 리스트 맨 뒤 키를 꺼내 해시맵·리스트에서 지우고 `used_memory -= victim.size`, `evicted_keys += 1`을 반복합니다.
5. **종료 조건**: `used_memory <= maxmemory`. 방금 넣은 키는 MRU이고 2단계에서 크기가 한도 이하임을 확인했으므로 마지막까지 남습니다.

예시: maxmemory 20에 3바이트 키 4개(12) 상태에서 15바이트 `big`을 넣으면 27 → k0(24) → k1(21) → k2(18) 순으로 3개를 지우고 멈춥니다. 무작위 5,000회 연산마다 `used_memory`가 실제 합계와 같고 한도를 넘지 않는지 테스트로 검사합니다.

### 3-5. GET 전체 흐름: TTL 확인 → 삭제 여부 → 값 반환 → LRU 갱신 조건 ✅

📂 `Store.get` (주석에 단계 번호 표기) · 🧪 `test_get_on_expired_key_deletes_and_returns_none`, `test_get_refreshes_lru`

**답변.**

```
0) (명령 공통) 힙 루트부터 이미 만료된 키 일괄 정리 — active expiration
1) HashMap.get(key)로 Entry 조회                         O(1)
2) Entry가 없으면 → (nil)
3) expire_at <= now 이면 → 데이터·LRU에서 삭제, used_memory 감소 → (nil)
   ※ 반환에 실패했으므로 LRU는 갱신하지 않는다
4) 살아있으면 → move_to_front(entry.lru_node)로 MRU 갱신   O(1)
5) "value" 반환
```

LRU 갱신을 "반환 성공 시에만" 하는 이유는, 없는 키나 만료된 키를 조회한 것은 데이터를 사용한 것이 아니기 때문입니다. 같은 이유로 EXISTS도 LRU를 갱신하지 않도록 했습니다(`test_exists_does_not_refresh_lru`).

---

## 항목 4. 확장 질문

### 4-1. LRU 대신 LFU를 구현한다면 자료구조를 어떻게 바꿔야 하는가

📄 상세 설계(빈도 카운터 방식, 자료구조 3안 비교, Store 변경 지점, LRU와 제거 결과가 갈리는 예시): [`design.md` 8.1](design.md#81-lru--lfu-전환)

**답변.** LFU는 "가장 적게 사용된 키"를 제거하므로, 사용 횟수(빈도)별로 키를 묶어야 합니다. O(1) LFU의 대표 구조는 다음과 같습니다.

```
key_map  : HashMap[key → Entry(value, freq, node)]
freq_map : HashMap[freq → DoublyLinkedList[key]]    ← 같은 빈도 안에서는 LRU 순서
min_freq : 현재 가장 작은 빈도
```

- **접근 시**: 키를 `freq` 리스트에서 떼어(`remove_node`, O(1)) `freq+1` 리스트 앞에 붙입니다. 예전 리스트가 비었고 그게 `min_freq`였다면 `min_freq += 1`
- **새 키**: `freq = 1` 리스트에 넣고 `min_freq = 1`
- **제거**: `freq_map[min_freq]` 리스트의 맨 뒤 (빈도가 같으면 오래된 것부터)

지금 구조에서 재사용할 수 있는 것은 이중 연결 리스트와 해시맵 전부입니다. 바뀌는 곳은 `Store`의 `_lru` 한 개 리스트가 "빈도별 리스트 묶음"으로 바뀌는 부분뿐이고, 명령어·출력 계층은 수정할 필요가 없습니다. 실무에서는 오래전에 많이 쓰인 키가 영원히 남는 문제를 막기 위해 빈도를 주기적으로 감쇠(Redis의 `lfu-decay-time`)시킵니다.

### 4-2. 데이터가 10만 건으로 늘면 병목은 어디이고 어떻게 개선하는가

근거 데이터: `python scripts/benchmark.py` → [`benchmark.md`](benchmark.md)

📄 단계별 측정(리사이즈 비중, KEYS 수집·렌더링 분리, 엔트리당 메모리)과 샤딩·병렬화·I/O 대책: [`benchmark.md` 10만 건 규모 병목 분석](benchmark.md#10만-건-규모-병목-분석)

**답변.** 측정해 보면 GET은 10만 건에서도 처리량이 유지되지만, 다음 지점에서 비용이 드러납니다.

| 병목 | 원인 | 개선 |
| --- | --- | --- |
| **리사이즈 순간 지연** | 로드 팩터 초과 시 한 번에 전체 재해싱 (10만 건 규모에서 SET 한 번이 수백 ms 걸리는 순간이 생김 — 벤치마크의 `max SET ms`) | 두 테이블을 두고 명령마다 버킷 몇 개씩 옮기는 **점진적 리해싱** (Redis 방식) 또는 예상 크기로 미리 할당 |
| **KEYS** | 전체 순회 O(n), 결과 배열 생성 | 커서 기반 `SCAN`으로 나눠서 반환 |
| **대량 동시 만료** | 같은 시각에 만료되는 키 k개를 한 명령에서 모두 처리 O(k log n) → 그 명령이 오래 걸림 | 한 번에 처리할 만료 개수/시간에 상한을 두고 나머지는 다음 명령에서 처리 (Redis의 active expire cycle) |
| **TTL 힙 stale 누적** | 같은 키에 EXPIRE 반복 시 옛 항목이 쌓임 | 이미 구현: stale이 살아있는 TTL 키의 2배를 넘으면 재구성 |
| **노드 메모리** | 키마다 Entry + LRU 노드 + 체인 노드 객체 | `__slots__`로 이미 절감. 더 줄이려면 근사 LRU(샘플링)로 리스트 자체 제거 |
| **파이썬 해시 계산** | 바이트마다 파이썬 반복문 | 긴 키에서 비용 증가 → 실무라면 C 확장이나 내장 해시 사용 |

### 4-3. used_memory에 자료구조 오버헤드까지 포함하면 무엇이 달라지고, 공정한 비교를 위해 어떤 보정이 필요한가

📄 실측 오버헤드(`scripts/memory_overhead.py`), 과제 예시를 다른 모델로 재생한 결과, 보정 방법과 채점 영향 표: [`design.md` 8.2](design.md#82-used_memory-모델-변경의-영향)

**답변.** 지금 공식은 키와 값의 바이트만 셉니다. 오버헤드(노드 객체, 포인터, 버킷 배열, 힙 배열, Entry 객체)를 포함하면 다음이 달라집니다.

- **같은 데이터라도 used_memory가 훨씬 커집니다.** 파이썬 객체는 작은 객체도 수십 바이트라, 5바이트 값에 수백 바이트가 붙을 수 있습니다.
- **값이 변하지 않아도 used_memory가 변합니다.** 해시맵이 리사이즈하면 버킷 배열이 2배가 되어 사용량이 계단식으로 뜁니다. 그래서 같은 SET 순서라도 "어느 시점에 리사이즈가 일어났는지"에 따라 제거되는 키가 달라집니다.
- **환경에 따라 달라집니다.** `sys.getsizeof` 값은 파이썬 버전, 32/64비트, 구현체(CPython/PyPy)마다 다릅니다.
- **TTL 힙의 stale 항목**도 메모리에 포함되어, lazy deletion 정책이 제거 결과에 영향을 줍니다.

공정한 비교·채점을 위한 보정:

1. **결정적인 비용 모델 사용**: 실제 측정(`getsizeof`) 대신 "엔트리당 고정 오버헤드 C바이트 + 키 + 값"처럼 명세로 정한 상수 모델을 씁니다(Redis 문서도 `used_memory`를 근사치로 다룹니다).
2. **구조 오버헤드 분리 표기**: `used_memory_dataset`(키+값)과 `used_memory_overhead`(구조)를 나눠 보고하고, eviction 판단은 dataset 기준으로 합니다(Redis INFO와 같은 방식).
3. **리사이즈 비용 평준화**: 버킷 배열은 "현재 엔트리 수 / 0.75" 같은 이론값으로 계산해 리사이즈 타이밍에 따른 계단 효과를 없앱니다.
4. **환경 고정**: 실제 측정을 쓴다면 파이썬 버전과 플랫폼을 고정하고 결과에 함께 기록합니다.

---

### 부록: 테스트 실행

```bash
python -m unittest discover -s tests -t . -v
```

테스트는 106개입니다. GitHub Actions(`.github/workflows/tests.yml`)가 push마다 Python 3.8 · 3.10 · 3.12 · 3.13 · 3.14에서 자동으로 실행하고, `uv run scripts/ci_local.py`로 같은 단계를 로컬에서 실행할 수 있습니다.
