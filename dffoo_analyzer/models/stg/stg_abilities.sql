WITH

final AS (
    SELECT
        char_name::VARCHAR                   AS char_name
        , ability_name::VARCHAR              AS ability_name
        , ability_id::INTEGER                AS ability_id
        , main_target_hp_attacks::SMALLINT   AS main_target_hp_attacks
        , non_target_hp_attacks::SMALLINT    AS non_target_hp_attacks
        , hp_dmg_cap_up_perc::SMALLINT       AS hp_dmg_cap_up_perc
        , attribute_list::TEXT               AS attribute_list
        , game_version::CHARACTER(2)         AS game_version
        , scrape_started_at_utc::TIMESTAMP   AS scrape_started_at_utc
        , scrape_ended_at_utc::TIMESTAMP     AS scrape_ended_at_utc
    FROM {{ source('web_scraper', 'raw_abilities') }}
)

SELECT * FROM final