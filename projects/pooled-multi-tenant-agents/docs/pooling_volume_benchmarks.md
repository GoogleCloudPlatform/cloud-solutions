# Empirical Volume, QoS & FinOps Benchmarks: Why High-Density Pooling Wins (Pattern A)

This benchmark report is generated deterministically by
[`scripts/benchmark_pooling_at_scale.py`](../scripts/benchmark_pooling_at_scale.py)
(`make benchmark`) and validates the quantitative benefits of **Pattern A
(High-Density Pooled Architecture)** at scale.

---

## 1. High-Volume Scale & Connection Multiplexing Benchmark (`N = 250` Tenants, `2,500` Concurrent Turns)

| Metric                                     | Siloed Baseline ($N = 250$ Dedicated Projects)           | Pattern A Pooled Result (Measured)                                 |
| :----------------------------------------- | :------------------------------------------------------- | :----------------------------------------------------------------- |
| **Tenant Onboarding Latency ($N = 250$)**  | ~25 mins per tenant (`terraform apply` per silo)         | **`19.48 ms` total (`0.078 ms` / tenant — $O(1)$ metadata write)** |
| **Database Connections Required**          | `1,250` idle connections (min 5 per silo)                | **`25` physical connections (`100x` multiplexing ratio)**          |
| **Total Concurrent 5-Hop Turns Executed**  | `2,500`                                                  | **`2,500` (`628 turns/sec`)**                                      |
| **Cross-Tenant Data, Tool, or OTel Bleed** | `0` (physical isolation)                                 | **`0` (100% cryptographic + `SET LOCAL` RLS isolation)**           |
| **5-Hop Turn Latency (P50 / P95 / P99)**   | High cold-start variance (8,000-15,000 ms on cold silos) | **`P50: 1.51 ms` • `P95: 2.37 ms` • `P99: 3.09 ms`**               |

---

## 2. Priority QoS Scheduling Under a 15x Traffic Storm (Defeating Head-of-Line Blocking)

When 60 concurrent Standard-tier turns (**RetailStream Corp**, `priority=10`)
saturate a 4-connection pool while 10 P1 Enterprise turns (**FinVault Bank**,
`priority=0`) arrive:

| Metric                                | Standard Tier (Best-Effort Queue) | Enterprise Tier (Priority Preemption)   |
| :------------------------------------ | :-------------------------------- | :-------------------------------------- |
| **Median Connection Queue Wait Time** | `37.58 ms`                        | **`2.02 ms` (`18.6x` faster checkout)** |
| **Head-of-Line Blocking**             | Absorbs queue backpressure        | **Preempts Standard queue immediately** |

---

## 3. Cross-Tenant Prompt Prefix Cache Amortization (Pooled vs. Siloed AI Tokenomics)

Assuming a `16,384`-token shared system instruction + base MCP schema prefix
(`ContextCacheConfig`, `TTL = 1 hr`, `90%` cached input token discount) and
`1,616` dynamic tenant tokens per turn (`18,000` total raw input tokens/turn):

| Active Tenants ($N$) | Daily Agent Turns | Siloed Cache Hit Rate | Pooled Cache Hit Rate | Siloed Billable Input Tokens | Pooled Billable Input Tokens | Net Pooled COGS Advantage |
| :------------------- | :---------------- | :-------------------- | :-------------------- | :--------------------------- | :--------------------------- | :------------------------ |
| **10**               | 60                | `0.0%`                | **`60.00%`**          | 1,080,000 tokens/day         | **549,144 tokens/day**       | **`49.1%` Lower COGS**    |
| **100**              | 600               | `0.0%`                | **`96.00%`**          | 10,800,000 tokens/day        | **2,306,304 tokens/day**     | **`78.7%` Lower COGS**    |
| **500**              | 3,000             | `0.0%`                | **`99.20%`**          | 54,000,000 tokens/day        | **10,115,904 tokens/day**    | **`81.3%` Lower COGS**    |
| **1,000**            | 6,000             | `0.0%`                | **`99.60%`**          | 108,000,000 tokens/day       | **19,877,904 tokens/day**    | **`81.6%` Lower COGS**    |
