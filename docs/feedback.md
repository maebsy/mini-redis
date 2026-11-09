# 동료 평가 피드백 반영 내역

동료 평가 17개 항목의 "부족한 점"과 "보완" 요청을 하나씩 반영한 체크리스트입니다(2026-11-09).
평가 결과는 PASS 14개, FAIL 3개(#15 · #16 · #17)였습니다. FAIL 항목의 답변은 [`checklist.md`](checklist.md) 4장과 발표 45~52쪽에 있었지만 설계 문서에 없었습니다. 그래서 [`design.md`](design.md) · [`benchmark.md`](benchmark.md)에 측정값과 함께 다시 쓰고 서로 링크했습니다.

- 코드 변경: #6 (docstring), #13 (`DEBUG EVICTIONS`) 두 곳. 테스트 101개 → 106개
- 측정 스크립트 4개 추가: `scripts/hash_distribution.py`, `scripts/ttl_heap_stats.py`, `scripts/profile_100k.py`, `scripts/memory_overhead.py`. 문서의 모든 수치는 Python 3.14.4 / Linux에서 이 스크립트로 잰 값입니다
- 발표 자료: 코드 해부 슬라이드의 줄 번호를 바뀐 코드에 맞춰 다시 매김, 테스트 수 갱신, 부록 A6~A11 추가 (73장 → 79장)

## 체크리스트

| # | 평가 | 부족한 점 (요약) | 보완 요청 | 반영 내용 | 위치 |
| --- | --- | --- | --- | --- | --- |
| 1 | PASS | KEYS 패턴 매칭 한계 설명 | README에 예시로 표기 | ✅ `KEYS` / `KEYS *` / `KEYS user:*` 실제 실행 결과, 접두사 검색 대안(`DEBUG RANGEKEYS user: user;`), O(n) 비용(10만 건 수집 60 ms + 출력 467 ms) | [README › KEYS 의 한계](../README.md#keys-의-한계) |
| 2 | PASS | 샘플링 LRU 등 정책 비교 없음 | CONFIG SET 후 제거 정책과 여러 키 제거 순서 사례 | ✅ maxmemory 30 → 15 축소 시 b → c → d 순서로 빠지는 실제 실행 결과와 단계표, 정책 6종(정확한 LRU · Redis 근사 LRU · random · volatile-* · LFU · noeviction) 비교표, 정확한 LRU를 고른 이유 | [design.md 3.3](design.md#config-set-maxmemory-축소와-여러-키-제거-순서), [제거 정책 비교](design.md#제거-정책-비교), 슬라이드 A10 |
| 3 | PASS | INFO 메트릭 단위 설명이 짧음 | 단위와 계산식(UTF-8 기준) 부연 | ✅ INFO의 모든 필드(memory · stats · keyspace)의 단위 · 계산식 · 초기화 시점 표, 한글 키 예시(`SET 이름 "김철수"` → 15바이트) 실행 결과 | [design.md 3.7](design.md#37-info-출력값의-단위와-계산), [README › INFO memory 값의 단위](../README.md#info-memory-값의-단위) |
| 4 | PASS | 만료 예외 케이스 정리 부족 | EXPIRE(0 이하)와 힙 stale 항목 예시 | ✅ 예외 케이스 표 7종, stale 항목이 생기고(재설정 · DEL · SET 덮어쓰기) 꺼낼 때 버려지는 과정의 실제 `DEBUG TTLHEAP` 출력 | [design.md 3.5 예외 케이스](design.md#예외-케이스) |
| 5 | PASS | 사용자 안내 예시 부족 | 자주 발생하는 에러 케이스를 README에 | ✅ 에러 12가지의 입력 · 출력 · 원인 · 해결 표 (모두 실제 출력) | [README › 자주 발생하는 에러](../README.md#자주-발생하는-에러) |
| 6 | PASS | 복잡도 근거가 테스트에만 있음 | linked_list 모듈에 상수 포인터 교체 수 주석 | ✅ 6개 공개 메서드 docstring에 포인터 수 명시(줄 수는 그대로 유지해 슬라이드 줄 번호 보존). `_unlink`가 떼어낸 노드도 정리한다는 점을 반영해 design.md 표도 정정 | `mini_redis/structures/linked_list.py` 90~129줄, [design.md 2.1](design.md#21-이중-연결-리스트--linked_listpy) |
| 7 | PASS | 해시 품질 실험이 요약뿐 | 해시 분포 결과를 표로 | ✅ 키 집합 4종 × 1천 · 1만 · 10만 건의 빈 버킷 비율 · 평균 체인을 포아송 이론값과 비교, χ²/df, 나쁜 해시(바이트 합) 비교군 | [design.md 해시 분포 실험](design.md#해시-분포-실험), `scripts/hash_distribution.py`, 슬라이드 A7 |
| 8 | PASS | 노드 재사용 전략 언급 제한적 | 체인 노드 생성 · 해제 비용과 재사용 전략 | ✅ 연산별로 생성 · 해제되는 객체 표, 리사이즈 때 `_Entry`는 재사용하고 체인 노드는 다시 만든다는 점, CPython 해제 방식, 실측 메모리, 재사용 대안 4가지 비교 | [design.md 체인 노드의 생성·해제 비용과 재사용](design.md#체인-노드의-생성해제-비용과-재사용) |
| 9 | PASS | 리해시 원자성 · 성능 영향 설명 간략 | 리해시 비용과 점진적 리해싱 대안 | ✅ 리사이즈별 실측 시간(마지막 확장 298 ms, SET 전체의 44%), 단일 스레드 원자성과 꼬리 지연, 점진적 리해싱 의사코드와 8 → 16 단계 예시, 대안 4가지 비교표 | [design.md 리해시 비용과 대안](design.md#리해시-비용과-대안) |
| 10 | PASS | 두 구조 협력의 예외 시퀀스 부족 | 삽입/삭제/만료 sequence diagram | ✅ Mermaid 시퀀스 다이어그램 3개(SET + 제거, DEL, active · lazy 만료), 연산 × 구조 영향 표 | [design.md 세 구조의 동기화 순서](design.md#세-구조의-동기화-순서) |
| 11 | PASS | 동시성에서 O(1) 한계 언급 없음 | design.md에 명시 | ✅ 읽기도 쓰기인 LRU, 여러 구조에 걸친 불변식, O(1) ≠ 응답 시간, GIL의 한계, 대안 4가지와 Redis의 선택 | [design.md 동시성에서의 O(1) 보장 한계](design.md#동시성에서의-o1-보장-한계), 슬라이드 A11 |
| 12 | PASS | 힙 재구성 복잡도 산정이 간단 | 재구성 빈도와 복잡도 추정(측정 기반) | ✅ 워크로드 7종의 재구성 횟수 · 최대 힙 크기 · EXPIRE 1회 비용 측정, 분할 상환 O(log n) 근거 | [design.md stale 항목과 재구성 빈도](design.md#stale-항목과-재구성-빈도), `scripts/ttl_heap_stats.py`, 슬라이드 A7 |
| 13 | PASS | 누가 제거됐는지 관찰 불가 | DEBUG/INFO에 최근 제거 리스트 | ✅ **코드 추가**: `Store.recent_evictions`(최대 16개 Deque), `DEBUG EVICTIONS [count]`, 테스트 5개, `examples/02_lru.txt`에 시연 추가 | `mini_redis/store.py` 117줄, `mini_redis/server.py` `_cmd_debug`, [design.md 3.8](design.md#38-제거-기록-관찰-debug-evictions) |
| 14 | PASS | 만료 동시성 등 에지케이스 설명 없음 | GET과 expire_due_keys 호출 시점 관계 | ✅ `Server.execute`의 줄 번호 순서, t1(active) · t2(lazy) 시간선, 에러 명령은 active 만료를 하지 않는다는 점 | [design.md GET 과 expire_due_keys 의 호출 시점](design.md#get-과-expire_due_keys-의-호출-시점) |
| 15 | **FAIL** | LFU 전환에 대한 기술이 설계 문서에 없음 | usage counter, 우선순위 큐/버킷 구조, 정책 비교 | ✅ 정확한 카운터 vs Redis 로그 카운터 · 감쇠, 자료구조 3안 비교(빈도 버킷 · 힙 · 샘플링), Store 메서드별 변경 지점과 추가할 테스트, LRU와 다른 키가 지워지는 예시, 상황별 유리한 정책 | [design.md 8.1](design.md#81-lru--lfu-전환), 슬라이드 A11 |
| 16 | **FAIL** | 10만 건 병목(샤딩 · 병렬화 · I/O) 식별 부족 | 10만 건 병목 분석 추가 | ✅ 단계별 실측(해시 · 리사이즈 · GET · KEYS 수집/렌더링/쓰기 · 대량 만료 · 메모리), 병목 6개의 원인과 대책, 샤딩 설계와 트레이드오프, GIL과 프로세스 병렬화, I/O(SCAN · 파이프라이닝 · 이벤트 루프), 개선 우선순위 | [benchmark.md 10만 건 규모 병목 분석](benchmark.md#10만-건-규모-병목-분석), `scripts/profile_100k.py`, 슬라이드 A8 |
| 17 | **FAIL** | used_memory 모델 변경의 채점 영향 분석 없음 | 오버헤드 포함/미포함 보정 방법과 채점 영향 | ✅ 실측 오버헤드(엔트리당 약 575 B, 키+값의 약 28배), 과제 예시를 C = 0 · 16 · 48 · 575 모델로 재생한 결과, 달라지는 것 5가지, 포함/미포함 보정 방법 · 채점 영향 표, Python 3.8과 3.14의 실측 차이 | [design.md 8.2](design.md#82-used_memory-모델-변경의-영향), `scripts/memory_overhead.py`, 슬라이드 A9 |

## 확인 방법

```bash
python -m unittest discover -s tests -t .      # 106개
python main.py < examples/02_lru.txt           # 마지막에 DEBUG EVICTIONS
python3 scripts/hash_distribution.py           # #7  (약 40초)
python3 scripts/ttl_heap_stats.py              # #12
python3 scripts/profile_100k.py                # #16 (약 15초)
python3 scripts/memory_overhead.py             # #17 (약 10초)
```
