# LumApps Event Audit & Deduplication Analysis

## Table of Contents
1. [Overview]
2. [Analysis 1: General Stats Checks]
3. [Analysis 2: Object ID Field Discovery]
4. [Analysis 3: Deduplication Analysis]
5. [Key Findings]

## Overview

**Purpose:** To understand quality of Lumapps events which are taken for product 'Jobs Done' metrics and to identify "object_id" fields for event deduplication.

**Time Period:** Last 180 days (for deduplication analysis)  
**Data Source:** `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`  
**Events Analyzed:** 6 events (content-viewed, community-viewed, post-viewed, video-played, comment-created, reaction-created) taken for 2026.1 Jobs done iteration. This quality and deduplication analysis should be repeated for every new event that is added to Jobs Done metric.

---

## Analysis 1: General Stats Checks

### Purpose
To understand the adoption of product domains, usage patterns, and maturity of events across the LumApps platform before performing deduplication analysis.

### Why This Matters
1. **Identify widely used vs. niche features** - Understand which events have broad adoption
2. **Determine event maturity** - Which events are active (recent) or legacy (deprecated)
3. **Prioritize Jobs Done metrics** - See the full event landscape to decide what to track
4. **Establish baseline** - Create comparison point with Beekeeper event patterns

### What This Analysis Tells Us

#### Customer/Organization Adoption
- `unique_orgs` = How many organizations use this event
- `pct_of_orgs` = % of ALL customers in the system who use this event
- **Insight:** Differentiates between universal features (>50% org adoption) vs. niche features (<10% org adoption)

#### User Adoption
- `unique_users` = How many individual users have used this event
- `pct_of_users` = % of ALL users in the system who have used this event
- **Insight:** Shows actual user engagement beyond just organizational adoption

#### Event Maturity & Status
- `first_seen_ever` = When this event first appeared in the system
- `last_seen_ever` = Most recent occurrence of this event
- **Insight:** Identifies mature features (2+ years old), new features (<90 days), and potentially deprecated events

#### Event Granularity
- Multiple rows for same action_type with different result_type values
- Example: `ReactAction` with result_type = "like" vs "unlike"
- **Insight:** Shows level of detail captured in events

### Query

```sql

WITH total_counts AS (
  SELECT 
    COUNT(DISTINCT organization_id) as total_org_count,
    COUNT(DISTINCT CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING))) as total_user_count
  FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
  -- No WHERE clause - count ALL users and orgs in the entire table
),

parsed_events AS (
  SELECT 
    action_type,
    target.type as target_type,
    result.type as result_type,
    target.id as target_id,
    COALESCE(result.type, target.type) as object_type,
    product_name,
    organization_id,
    user_id,
    action_time
  FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
  WHERE action_type IN ('ViewAction', 'CommentAction', 'CreateAction', 'PlayAction', 'ReactAction', 'MultiReactAction')
),

filtered_events AS (
  SELECT *
  FROM parsed_events
  WHERE 
    -- Content viewed
    (action_type = 'ViewAction' AND target_type = 'Content')
    -- Community viewed
    OR (action_type = 'ViewAction' AND target_type = 'Community')
    -- Post viewed
    OR (action_type = 'ViewAction' AND target_type = 'Post')
    -- Video played
    OR (action_type = 'PlayAction' AND target_type = 'video')
    -- Comment created
    OR (action_type = 'CommentAction')
    -- Reaction created
    OR (action_type IN ('ReactAction', 'MultiReactAction'))
)

SELECT 
  action_type,
  target_type,
  result_type,
  object_type,
  product_name,
  COUNT(*) as total_events,
  COUNT(DISTINCT organization_id) as unique_orgs,
  COUNT(DISTINCT CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING))) as unique_users,
  ROUND(COUNT(DISTINCT organization_id) / (SELECT total_org_count FROM total_counts) * 100, 2) as pct_of_orgs,
  ROUND(COUNT(DISTINCT CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING))) / (SELECT total_user_count FROM total_counts) * 100, 2) as pct_of_users,
  MIN(action_time) as first_seen_ever,
  MAX(action_time) as last_seen_ever
FROM filtered_events
GROUP BY action_type, target_type, result_type, object_type, product_name
ORDER BY action_type, total_events DESC;
```

## Analysis 2: Identify Object ID Field 

### Purpose
To understand how to calculate **unique user-object pairs** for deduplication analysis.

### The Problem
In LumApps event table, we have multiple fields with IDs (not one JSON payload like in Beekeeper):
- `id` (event ID)
- `target.id` (target object ID)
- `target.type` (target object type)
- `result.id` (result object ID)
- `result.type` (result object type)
- `context.id` (context object ID)
- `context.type` (context object type)

**Without identifying the correct object_id field, we cannot:**
- Accurately measure the percentage of events which are duplicates
- Identify events with the same user + object that happen within ≤1s
- Check data quality (are IDs/object_ids/user_ids always present?)

### What is a User-Object Pair?
When a user views content multiple times, we need to know which field contains the content_id to properly count unique (user, content) pairs.


### The Approach
We take all fields with IDs and check for patterns across events to identify which field contains the object_id for each event type.

### The Outcome: The schema follows a consistent pattern

```
target_type → target.id
result_type → result.id
context_type → context.id
```

**Examples:**
- `target_type = "Article"` → `target.id` = article_id
- `result_type = "Comment"` → `result.id` = comment_id
- `context_type = "Community"` → `context.id` = community_id


### Query

```sql
-- Purpose: Identify which field contains object_id for each event type

SELECT 
  action_type,
  target.type as target_type,
  result.type as result_type,
  context.type as context_type,
  product_name,
  
  -- Sample size
  COUNT(*) as total_events,
  
  -- Event ID (primary key?)
  COUNTIF(id IS NOT NULL) as has_id,
  ROUND(COUNTIF(id IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_id,
  
  -- Target fields
  COUNTIF(target.id IS NOT NULL) as has_target_id,
  ROUND(COUNTIF(target.id IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_target_id,
  
  -- Result fields
  COUNTIF(result.id IS NOT NULL) as has_result_id,
  ROUND(COUNTIF(result.id IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_result_id,
  
  -- Context fields (NOT used for deduplication)
  COUNTIF(context.id IS NOT NULL) as has_context_id,
  ROUND(COUNTIF(context.id IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_context_id,
  COUNTIF(context.type IS NOT NULL) as has_context_type,
  ROUND(COUNTIF(context.type IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_context_type,
  
  -- User fields
  COUNTIF(user_id IS NOT NULL) as has_user_id,
  ROUND(COUNTIF(user_id IS NOT NULL) * 100.0 / COUNT(*), 2) as pct_with_user_id

FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`

WHERE 
  -- Content viewed
  (action_type = 'ViewAction' AND target.type = 'Content')
  -- Community viewed
  OR (action_type = 'ViewAction' AND target.type = 'Community')
  -- Post viewed
  OR (action_type = 'ViewAction' AND target.type = 'Post')
  -- Video played
  OR (action_type = 'PlayAction' AND target.type = 'video')
  -- Comment created
  OR (action_type = 'CommentAction')
  -- Reaction created
  OR (action_type IN ('ReactAction', 'MultiReactAction'))

GROUP BY action_type, target_type, result_type, context_type, product_name
ORDER BY action_type, target_type, total_events DESC;
```

## Analysis 3: Deduplication Analysis

### Purpose
To measure data quality and identify duplicate events by analyzing unique user-object pairs and applying 1-second deduplication logic.

### Why This Matters
1. **Measure event quality** - How many events are true duplicates vs. legitimate repeat actions?
2. **Inform deduplication strategy** - Should we apply 1s dedup? What's the impact?
3. **Compare with Beekeeper** - Are patterns similar across platforms?
4. **Validate data completeness** - Are object_ids and user_ids always present?

### Deduplication Logic

**Methodology (matching Beekeeper):**
- **Partition by:** `user_id` (org_id + user_id), `object_id`
- **Threshold:** 1 second (1000 milliseconds)
- **Rule:** Same user + same object within 1 second = duplicate

**User Uniqueness (Multi-Tenancy):**
```sql
user_id = CONCAT(organization_id, '-', user_id)
```
- Must concatenate `organization_id + user_id` for true uniqueness

**Window Function Logic:**
```sql
LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time)
```
- For each user-object pair, look at previous occurrence
- Calculate time difference in milliseconds
- If ≤1000ms → duplicate
- If >1000ms or NULL (first occurrence) → keep


### Query

```sql
-- This query replicates Beekeeper deduplication analysis for 6 LumApps events
-- Time filter: Last 180 days

-- CONTENT-VIEWED
WITH content_viewed_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        target.id as object_id,
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type = 'ViewAction'
      AND target.type = 'Content'
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
content_viewed_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM content_viewed_base
),
content_viewed_stats AS (
    SELECT
        'content-viewed' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM content_viewed_dedup
),

-- COMMUNITY-VIEWED
community_viewed_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        target.id as object_id,
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type = 'ViewAction'
      AND target.type = 'Community'
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
community_viewed_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM community_viewed_base
),
community_viewed_stats AS (
    SELECT
        'community-viewed' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM community_viewed_dedup
),

-- POST-VIEWED
post_viewed_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        target.id as object_id,
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type = 'ViewAction'
      AND target.type = 'Post'
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
post_viewed_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM post_viewed_base
),
post_viewed_stats AS (
    SELECT
        'post-viewed' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM post_viewed_dedup
),

-- VIDEO-PLAYED
video_played_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        target.id as object_id,
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type = 'PlayAction'
      AND target.type = 'video'
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
video_played_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM video_played_base
),
video_played_stats AS (
    SELECT
        'video-played' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM video_played_dedup
),

-- COMMENT-CREATED
comment_created_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        result.id as object_id,  -- Comment ID that was created
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type = 'CommentAction'
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
comment_created_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM comment_created_base
),
comment_created_stats AS (
    SELECT
        'comment-created' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM comment_created_dedup
),

-- REACTION-CREATED
reaction_created_base AS (
    SELECT
        CONCAT(CAST(organization_id AS STRING), '-', CAST(user_id AS STRING)) as user_id,
        target.id as object_id,  -- Object being reacted to
        action_time
    FROM `lumapps-internal-bi.bi_hm_prod_cells.fct_enriched_user_actions__bi`
    WHERE action_type IN ('ReactAction', 'MultiReactAction')
      AND DATE(action_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)
),
reaction_created_dedup AS (
    SELECT
        user_id,
        object_id,
        action_time,
        LAG(action_time) OVER (PARTITION BY user_id, object_id ORDER BY action_time) as prev_occurrence
    FROM reaction_created_base
),
reaction_created_stats AS (
    SELECT
        'reaction-created' as event_type,
        COUNT(*) as total_events,
        COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) as unique_user_object_pairs,
        ROUND(COUNT(DISTINCT CONCAT(COALESCE(user_id, 'NULL'), '|', COALESCE(object_id, 'NULL'))) * 100.0 / COUNT(*), 2) as pct_unique_pairs,
        COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) as events_after_1s_dedup,
        ROUND(COUNTIF(prev_occurrence IS NULL OR TIMESTAMP_DIFF(action_time, prev_occurrence, MILLISECOND) > 1000) * 100.0 / COUNT(*), 2) as pct_after_1s_dedup,
        COUNTIF(object_id IS NOT NULL AND object_id != '') as events_with_object_id,
        ROUND(COUNTIF(object_id IS NOT NULL AND object_id != '') * 100.0 / COUNT(*), 2) as pct_with_object_id,
        COUNTIF(user_id IS NOT NULL AND user_id != '') as events_with_user_id,
        ROUND(COUNTIF(user_id IS NOT NULL AND user_id != '') * 100.0 / COUNT(*), 2) as pct_with_user_id
    FROM reaction_created_dedup
)

-- COMBINE ALL RESULTS
SELECT * FROM content_viewed_stats
UNION ALL
SELECT * FROM community_viewed_stats
UNION ALL
SELECT * FROM post_viewed_stats
UNION ALL
SELECT * FROM video_played_stats
UNION ALL
SELECT * FROM comment_created_stats
UNION ALL
SELECT * FROM reaction_created_stats
ORDER BY event_type;
```
