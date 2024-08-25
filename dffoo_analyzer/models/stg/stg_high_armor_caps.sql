WITH

final AS (
    SELECT
        char_name::VARCHAR                   AS char_name
        , personal_hp_dmg_cap_up::SMALLINT   AS personal_hp_dmg_cap_up
        , party_ha_hp_dmg_cap_up::SMALLINT   AS party_ha_hp_dmg_cap_up
        , game_version::CHARACTER(2)         AS game_version
        , scrape_started_at_utc::TIMESTAMP   AS scrape_started_at_utc
        , scrape_ended_at_utc::TIMESTAMP     AS scrape_ended_at_utc
    FROM {{ source('web_scraper', 'raw_high_armor_caps') }}
)

SELECT * FROM final