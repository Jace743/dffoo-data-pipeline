WITH

final AS (
    SELECT
        char_name::VARCHAR                      AS char_name
        , bt_personal_hp_dmg_cap_up::SMALLINT   AS bt_personal_hp_dmg_cap_up
        , bt_party_hp_dmg_cap_up::SMALLINT      AS bt_party_hp_dmg_cap_up
        , game_version::CHARACTER(2)            AS game_version
        , scrape_started_at_utc::TIMESTAMP      AS scrape_started_at_utc
        , scrape_ended_at_utc::TIMESTAMP        AS scrape_ended_at_utc
        , enemy_count_apply_list::TEXT          AS enemy_count_apply_list
    FROM {{ source('web_scraper', 'raw_bt_effects') }}
)

SELECT * FROM final