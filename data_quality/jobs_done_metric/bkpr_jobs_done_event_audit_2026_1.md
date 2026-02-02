# Beekeeper Events - Deduplication Analysis

## Table of Contents
1. [Overview]
2. [Analysis: Deduplication]
3. [Key Findings]

---

## Overview

**Purpose:** To measure data quality of Beekeeper events by analyzing 1-second deduplication rates for 20 events used in 'Jobs Done' metrics.

**Time Period:** Last 180 days  
**Data Source:** `production.beekeeper_events` (ClickHouse)  
**Events Analyzed:** 20 events across Documents, Surveys, Events, Navigation, Campaigns, Tasks, Reactions, Comments, Forms, Jobs, Streams, Shifts, and Chats taken for 2026.1 Jobs Done iteration. This quality and deduplication analysis should be repeated for every new event that is added to Jobs Done metric.

---

## Analysis: Deduplication

### Purpose

To measure 1-second deduplication metrics to assess data quality and identify accidental duplicates before implementing Jobs Done metrics.

### Why This Matters

1. **Detect technical issues** - Identify accidental double-clicks and rapid duplicate events
2. **Validate event source reliability** - Compare BACKEND vs FRONTEND data quality
3. **Inform Jobs Done implementation** - Understand which events need deduplication in dbt model
4. **Establish data quality baseline** - Document completeness of object_id and user_id fields

### What This Analysis Tells Us

- `total_events` = Raw event volume
- `unique_user_object_pairs` = Distinct (user, object) combinations
- `pct_unique_pairs` = % of events that are unique pairs (shows repeat behavior)
- `events_after_1s_dedup` = Events >1s apart from previous occurrence
- `pct_after_1s_dedup` = % remaining after 1s filter (data quality metric - higher is better)
- `with_object_id` / `with_user_id` = Data completeness metrics

### Deduplication Logic

All queries use the same approach:

1. **Extract events** from `production.beekeeper_events` (last 180 days)
2. **Prioritize event source**: Use BACKEND if available, otherwise FRONTEND
3. **Calculate time difference** between consecutive events for the same (user_id, object_id) pair using window function
4. **Count duplicates**: Events where time_diff ≤ 1000ms (1 second) are considered duplicates

**Window Function:**
```sql
lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp)
```

**Deduplication Rule:**
```sql
countIf(time_diff IS NULL OR time_diff > 1000) -- Keep first occurrence OR events >1s apart
```

### Query Structure

All 20 events follow this standard pattern:

```sql
-- [EVENT NAME]
WITH base_events AS (
    -- Extract user_id, object_id, timestamp, event_source
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, '[property_name]') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = '[event-name]'
      -- Prioritize BACKEND source
      AND event_source = (
        SELECT CASE 
          WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
          ELSE 'FRONTEND' 
        END
        FROM production.beekeeper_events
        WHERE event_type = '[event-name]' AND day >= today() - 180
      )
      AND day >= today() - 180
),
events_with_dedup AS (
    -- Calculate time difference from previous occurrence
    SELECT
        user_id, object_id, event_timestamp, event_source,
        lagInFrame(event_timestamp) OVER (
          PARTITION BY user_id, object_id 
          ORDER BY event_timestamp
        ) as prev_occurrence,
        dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
    FROM base_events
)
SELECT
    '[event-name]' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

### Object ID Extraction

Each event extracts its object_id from JSON properties using `JSONExtractString(event_properties_raw, 'property_name')`

### Event-Specific Filters

Some events require additional filters beyond the standard query structure - these filters where taken from udf dbt function jobs_done__udfs.sql

#### document-library-artifact-opened
**Filter:** Only count file opens (not folder navigation)
```sql
WHERE JSONExtractString(event_properties_raw, 'Artifact Type') = 'file'
```

#### navigation-extension-clicked / home-screen-shortcut-clicked / home-screen-shortcuts-widget-clicked
**Filter:** Only external URLs, exclude specific internal navigation IDs
```sql
WHERE JSONExtractString(event_properties_raw, 'Navigation Extension Type') = 'External URL'
  AND JSONExtractString(event_properties_raw, 'Navigation Extension ID') NOT IN (
    'a9792140-a852-4847-b05d-ca0580b57d2d',
    '6fd039a4-f73c-40e0-862c-ac9da97a6cda',
    'b2d49660-552e-11ed-9621-278f7a4bcc9f',
    'fab11255-311f-4a6b-ada6-e8661306461c'
  )
```

#### task-state-updated
**Filter:** Only count completion states (not intermediate states)
```sql
WHERE JSONExtractString(event_properties_raw, 'state') IN ('done', 'approved', 'rejected')
```

#### messages-read
**Special handling:** Message IDs are comma-separated, extract count from list
```sql
length(splitByChar(',', coalesce(JSONExtractString(event_properties_raw, 'message_id'), ''))) as event_count
-- Then use sum(event_count) instead of count() in final SELECT
```

#### user-calendar-retrieved
**Filter:** Only count when calendar has shifts (not empty retrievals)
```sql
WHERE JSONExtractInt(event_properties_raw, 'total_shifts') > 0
```

### Queries

#### 1. document-library-artifact-opened

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Artifact ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'document-library-artifact-opened'
      AND JSONExtractString(event_properties_raw, 'Artifact Type') = 'file'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'document-library-artifact-opened'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'document-library-artifact-opened' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 2. survey-completed

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'survey_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'survey-completed'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'survey-completed'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'survey-completed' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 3. company-event-opened

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Company Event ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'company-event-opened'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'company-event-opened'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'company-event-opened' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 4. navigation-extension-clicked

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Navigation Extension ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'navigation-extension-clicked'
      AND JSONExtractString(event_properties_raw, 'Navigation Extension ID') NOT IN (
                                                                                     'a9792140-a852-4847-b05d-ca0580b57d2d',
                                                                                     '6fd039a4-f73c-40e0-862c-ac9da97a6cda',
                                                                                     'b2d49660-552e-11ed-9621-278f7a4bcc9f',
                                                                                     'fab11255-311f-4a6b-ada6-e8661306461c'
        )
      AND JSONExtractString(event_properties_raw, 'Navigation Extension Type') = 'External URL'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'navigation-extension-clicked'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'navigation-extension-clicked' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 5. home-screen-shortcut-clicked

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Navigation Extension ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'home-screen-shortcut-clicked'
      AND JSONExtractString(event_properties_raw, 'Navigation Extension ID') NOT IN (
                                                                                     'a9792140-a852-4847-b05d-ca0580b57d2d',
                                                                                     '6fd039a4-f73c-40e0-862c-ac9da97a6cda',
                                                                                     'b2d49660-552e-11ed-9621-278f7a4bcc9f',
                                                                                     'fab11255-311f-4a6b-ada6-e8661306461c'
        )
      AND JSONExtractString(event_properties_raw, 'Navigation Extension Type') = 'External URL'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'home-screen-shortcut-clicked'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'home-screen-shortcut-clicked' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 6. home-screen-shortcuts-widget-clicked

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Navigation Extension ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'home-screen-shortcuts-widget-clicked'
      AND JSONExtractString(event_properties_raw, 'Navigation Extension ID') NOT IN (
                                                                                     'a9792140-a852-4847-b05d-ca0580b57d2d',
                                                                                     '6fd039a4-f73c-40e0-862c-ac9da97a6cda',
                                                                                     'b2d49660-552e-11ed-9621-278f7a4bcc9f',
                                                                                     'fab11255-311f-4a6b-ada6-e8661306461c'
        )
      AND JSONExtractString(event_properties_raw, 'Navigation Extension Type') = 'External URL'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'home-screen-shortcuts-widget-clicked'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'home-screen-shortcuts-widget-clicked' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 7. campaign-opened

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'campaign_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'campaign-opened'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'campaign-opened'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'campaign-opened' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 8. messages-read

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'message_id') as object_id,
        event_timestamp,
        event_source,
        length(splitByChar(',', coalesce(JSONExtractString(event_properties_raw, 'message_id'), ''))) as event_count
    FROM production.beekeeper_events
    WHERE event_type = 'messages-read'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'messages-read'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source, event_count,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'messages-read' as event_type,
    any(event_source) as event_source_K,
    sum(event_count) as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / sum(event_count), 2) as pct_unique_N,
    sumIf(event_count, time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(sumIf(event_count, time_diff IS NULL OR time_diff > 1000) * 100.0 / sum(event_count), 2) as pct_after_1s_P,
    sumIf(event_count, object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(sumIf(event_count, object_id IS NOT NULL AND object_id != '') * 100.0 / sum(event_count), 2) as pct_with_object_id_R,
    sumIf(event_count, user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(sumIf(event_count, user_id IS NOT NULL AND user_id != '') * 100.0 / sum(event_count), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 9. task-state-updated

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'task-state-updated'
      AND JSONExtractString(event_properties_raw, 'state') IN ('done', 'approved', 'rejected')
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'task-state-updated'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'task-state-updated' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 10. post-reaction-created

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'post_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'post-reaction-created'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'post-reaction-created'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'post-reaction-created' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 11. comment-liked

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'comment_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'comment-liked'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'comment-liked'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'comment-liked' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 12. chat-message-reacted

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'Message ID') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'chat-message-reacted'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'chat-message-reacted'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'chat-message-reacted' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 13. comment-created

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'comment-created'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'comment-created'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'comment-created' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 14. form-submitted

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'form-submitted'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'form-submitted'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'form-submitted' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 15. job-shared

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'job_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'job-shared'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'job-shared'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'job-shared' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 16. post-read

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'post-read'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'post-read'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'post-read' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 17. user-calendar-retrieved

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        event_id as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'user-calendar-retrieved'
      AND JSONExtractInt(event_properties_raw, 'total_shifts') > 0
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'user-calendar-retrieved'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'user-calendar-retrieved' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```

#### 18. message-created

```sql
WITH base_events AS (
    SELECT
        bkpr_actor_id_get_user_id(actor_id) as user_id,
        JSONExtractString(event_properties_raw, 'message_id') as object_id,
        event_timestamp,
        event_source
    FROM production.beekeeper_events
    WHERE event_type = 'message-created'
      AND event_source = (
        SELECT CASE
                   WHEN countIf(event_source = 'BACKEND') > 0 THEN 'BACKEND'
                   ELSE 'FRONTEND'
                   END
        FROM production.beekeeper_events
        WHERE event_type = 'message-created'
          AND day >= today() - 180
    )
      AND day >= today() - 180
),
     events_with_dedup AS (
         SELECT
             user_id, object_id, event_timestamp, event_source,
             lagInFrame(event_timestamp) OVER (PARTITION BY user_id, object_id ORDER BY event_timestamp) as prev_occurrence,
             dateDiff('millisecond', prev_occurrence, event_timestamp) as time_diff
         FROM base_events
     )
SELECT
    'message-created' as event_type,
    any(event_source) as event_source_K,
    count() as all_events_L,
    uniqExact((user_id, object_id)) as unique_pairs_M,
    round(uniqExact((user_id, object_id)) * 100.0 / count(), 2) as pct_unique_N,
    countIf(time_diff IS NULL OR time_diff > 1000) as after_1s_dedup_O,
    round(countIf(time_diff IS NULL OR time_diff > 1000) * 100.0 / count(), 2) as pct_after_1s_P,
    countIf(object_id IS NOT NULL AND object_id != '') as with_object_id_Q,
    round(countIf(object_id IS NOT NULL AND object_id != '') * 100.0 / count(), 2) as pct_with_object_id_R,
    countIf(user_id IS NOT NULL AND user_id != '') as with_user_id_S,
    round(countIf(user_id IS NOT NULL AND user_id != '') * 100.0 / count(), 2) as pct_with_user_id_T
FROM events_with_dedup;
```