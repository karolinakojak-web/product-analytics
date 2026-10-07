with 
-- Snapshot metrics (1–6) are measured as of the end date, capped at yesterday (last completed day)
least(toDate({{date_range_end}}), yesterday()) as snapshot_date,

org_units as (
    select id, name, unique_name, type, level, tenant_id 
    from `remote.monolith.mysql`.`org_units` 
    where tenant_id={{tenant_id}} 
), 

-- Segment BRN per org unit, taken from state-history so the format always matches
segments as (
    select distinct
        segment_brn,
        cityHash64(segment_brn)             membership_hash,
        splitByChar(':', segment_brn)[-1]   org_unit_id
    from `monolith.beekeeper.state-history.users`
    where tenant_id = toString({{tenant_id}})
        and toDate(at_date) = snapshot_date
),

-- 1, 2, 4. User counts by state as of snapshot_date
-- total    = all states incl. suspended (matches the previously sent report)
-- eligible = activated + created + invited (denominator for activation rate)
user_states as (
    select 
        splitByChar(':', segment_brn)[-1]                                    org_unit_id,
        sum(user_count)                                                      all_users,
        sumIf(user_count, user_state in ('activated', 'created', 'invited')) eligible_users,
        sumIf(user_count, user_state = 'suspended')                          suspended_users,
        sumIf(user_count, user_state = 'activated')                          activated_users
    from `monolith.beekeeper.state-history.users`
    where tenant_id = toString({{tenant_id}})
        and toDate(at_date) = snapshot_date
    group by org_unit_id
),

-- 5, 6. MAU (28 days) and WAU (7 days) ending on snapshot_date
active as (
    select 
        s.org_unit_id,
        uniq(a.actor_id)                                                            mau,
        uniqIf(a.actor_id, toDate(a.`timestamp`) >= snapshot_date - INTERVAL 6 DAY) wau
    from `analytics.beekeeper.materialized.activity-expanded` a
    inner join segments s on a.membership_hash = s.membership_hash
    where a.tenant_id = {{tenant_id}}
        and toDate(a.`timestamp`) between snapshot_date - INTERVAL 27 DAY and snapshot_date
    group by s.org_unit_id
),

events as (
    select 
        event_type, 
        actor_id, 
        event_timestamp,
        event_source,
        splitByChar(':', arrayJoin(memberships))[-1] org_unit_id,
        splitByChar(',', event_properties['chat_type'])[1] chat_type,
        event_properties['Artifact Type'] artifact_type
    from `analytics.beekeeper.events.tracking`
    where tenant_id={{tenant_id}} 
        and event_timestamp >= toDate({{date_range_start}})
        and event_timestamp <  toDate({{date_range_end}}) + INTERVAL 1 DAY  -- end date included in full
        and user_type='REGULAR'
        and event_type in (
            'message-created',
            'post-read',
            'post-created',
            'comment-created',
            'post-reaction-created',
            'form-created',
            'workflow-created',
            'survey-created',
            'document-library-artifact-uploaded',
            'stream-created'
        )
        and org_unit_id != toString(tenant_id)
),
totals as (
    select 
        org_unit_id,
        countIf(event_type='post-created' and event_source='BACKEND')          posts_created,      -- 7
        countIf(event_type='comment-created' and event_source='BACKEND')       comments_created,   -- 8
        countIf(event_type='post-reaction-created' and event_source='BACKEND') reactions_created,  -- 9
        countIf(event_type='post-read' and event_source='BACKEND')             posts_read,         -- 10
        countIf(event_type='form-created' and event_source='BACKEND')          forms_created,      -- 11
        countIf(event_type='workflow-created' and event_source='BACKEND')      workflows_created,  -- 12 (REGULAR + EMBEDDED)
        countIf(event_type='survey-created' and event_source='BACKEND')        surveys_created,    -- 13
        countIf(
            event_type='document-library-artifact-uploaded'
            and event_source='FRONTEND'
            and artifact_type='file'
        )                                                                      docs_uploaded,      -- 14
        countIf(event_type='stream-created' and event_source='BACKEND')        streams_created,    -- 15
        countIf(event_type='message-created' and chat_type='ONE_ON_ONE')       msg_sent_oneonone,  -- 16
        countIf(event_type='message-created' and chat_type='GROUP')            msg_sent_group      -- 17
    from events
    group by org_unit_id
)
select 
    o.id                                org_unit_id,
    o.name                              location_name,
    o.unique_name                       location_unique_name,
    o.level                             level,
    coalesce(us.all_users, 0)           total_users,          -- 1  (incl. suspended)
    coalesce(us.eligible_users, 0)      eligible_users,       --    helper: total minus suspended
    coalesce(us.suspended_users, 0)     suspended_users,      --    helper: total = eligible + suspended
    coalesce(us.activated_users, 0)     activated_users,      -- 4
    if(us.eligible_users > 0,
       round(us.activated_users / us.eligible_users * 100, 1),
       null)                            activation_rate_pct,  -- 2  (activated / eligible)
    if(us.activated_users > 0,
       min2(100, act.mau / us.activated_users * 100),
       null)                            engagement_rate_pct,  -- 3  (MAU / activated)
    coalesce(act.mau, 0)                mau,                  -- 5
    coalesce(act.wau, 0)                wau,                  -- 6
    coalesce(t.posts_created, 0)        posts_created,        -- 7
    coalesce(t.comments_created, 0)     comments_created,     -- 8
    coalesce(t.reactions_created, 0)    reactions_created,    -- 9
    coalesce(t.posts_read, 0)           posts_read,           -- 10
    coalesce(t.forms_created, 0)        forms_created,        -- 11
    coalesce(t.workflows_created, 0)    workflows_created,    -- 12
    coalesce(t.surveys_created, 0)      surveys_created,      -- 13
    coalesce(t.docs_uploaded, 0)        docs_uploaded,        -- 14
    coalesce(t.streams_created, 0)      streams_created,      -- 15
    coalesce(t.msg_sent_oneonone, 0)    msg_sent_oneonone,    -- 16
    coalesce(t.msg_sent_group, 0)       msg_sent_group        -- 17
from org_units o
left join totals t        on t.org_unit_id   = o.id
left join user_states us  on us.org_unit_id  = o.id
left join active act      on act.org_unit_id = o.id
where o.type = 'location'
order by o.level asc, o.name asc