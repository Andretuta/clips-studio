# Suíte completa do motor — 16/11/2026

Relatório conferido às 16h50 de Brasília.

## Resultado medido

- 5.480 aprovados, 119 falhas, 19 ignorados, zero erros: 5.618 testes.
- Duração no XML: 7.402,439 s (2 h 3 min 22,439 s). Início registrado: 14h41; relatório final gravado às 16h44.
- Os 40 testes de contrato passaram, incluindo os quatro casos de `test_cors_allows_desktop_and_dev_origins_only`.
- Código do CORS: `bea3eea`. O checkout compartilhado recebeu as mudanças Tauri durante a execução; esta suíte não representa um snapshot isolado de um único commit. Não houve comparação com uma base sem a alteração de CORS.
- Artefatos preservados, fora do commit: `D:/clipador-gta6/cache/cors-suite.log` e `D:/clipador-gta6/cache/cors-suite.xml`.

## Agrupamento das falhas

| Grupo | Falhas | Evidência e limite |
| --- | ---: | --- |
| Varreduras que incluem a .venv | 3 | As listas de infratores apontam `site-packages` da `.venv`. As exclusões em `test_binaries.py` e `test_scratch_cleanup.py` não incluem essa pasta. Separar dependências do código do projeto sem enfraquecer as verificações. |
| Expectativas e extração de texto da interface | 11 | Há regex sem correspondência e expectativas literais de textos envolvidos por tradução. A classificação agrupa os sintomas; não confirma equivalência funcional da interface. |
| Node: import de i18n ausente | 79 | 79 mensagens `ERR_MODULE_NOT_FOUND` apontam a `i18n`. Os harnesses copiam o módulo TypeScript para o temporário sem sua tradução. A falha ocorre antes da lógica que deveriam testar. |
| Encerramento dos vídeos (outro) | 12 | Inclui regeneração da mascote, chave do YAML e concatenação. O teste chama `python` sem caminho e a fixture lê o YAML local; o Python resolvido pelo PATH é 3.13 no C:, diferente da venv autorizada. Isso não explica sozinho todas as 12 falhas. Não alterar nem commitar a configuração local para fazê-las passar. |
| SDK, comandos Python e tutorial | 3 | Há divergência literal `py -m` versus `python -m` e falha do comando do tutorial via Bash. Conferir o intérprete e as regras específicas do Windows. |
| Legendas de segunda voz / marcador ASS q2 | 11 | 11 mensagens incluem o marcador ASS `\q2`; na amostra examinada, o teste esperava a mesma linha sem esse prefixo. Verificar a semântica e o vídeo antes de mudar expectativas. |

## Próximos passos

1. Corrigir o resolvedor dos testes Node para a tradução, sem esconder os testes de idiomas; repetir primeiro os 79 casos afetados.
2. Delimitar as varreduras ao código do projeto e repetir os três casos, mantendo a proteção contra recursos não fechados e downloads implícitos.
3. Isolar configuração e intérprete nos testes de outro/SDK; investigar separadamente as falhas de mídia.
4. Verificar os 11 casos de segunda voz com equivalência de legenda e uma amostra renderizada antes de alterar expectativas.
5. Depois dos grupos dirigidos, executar uma nova suíte completa sobre checkout estável. Não tratar as 119 falhas como regressões do CORS nem como anteriores a ele sem comparação.

O aceite anterior do Tauri continua delimitado a build, origem real, API, sessão, React, quadro de vídeo silenciado e inspeção da Mesa. Este relatório impede considerar a suíte ampla verde.

## Testes que falharam

### Varreduras que incluem a .venv

- `tests.test_binaries::test_yolo_weights_are_never_loaded_by_bare_name`
- `tests.test_scratch_cleanup::test_opencv_captures_all_go_through_the_helper`
- `tests.test_scratch_cleanup::test_cleanup_in_a_finally_never_calls_unlink`

### Expectativas e extração de texto da interface

- `tests.test_job_progress::test_stage_tables_match_the_app`
- `tests.test_plugin_docs::test_the_promise_sentence_is_the_apps`
- `tests.test_plugin_sdk_edit::test_the_choices_are_the_editors_own`
- `tests.test_ui_edit_suggestions::test_a_suggestion_reads_in_the_editors_own_words`
- `tests.test_ui_edit_suggestions::test_the_clip_panel_line_says_who_what_why_and_what_came_of_it`
- `tests.test_ui_edit_suggestions::test_the_promise_sentence_is_in_the_switch_title`
- `tests.test_ui_marketplace::test_the_marketplace_says_only_what_is_true_and_says_it_in_every_language`
- `tests.test_ui_steps::test_the_watch_editor_sends_kept_steps_back_and_clears_them_when_off`
- `tests.test_ui_steps::test_the_watch_editor_sends_kept_edit_plugins_back_and_clears_them_when_off`
- `tests.test_ui_steps::test_watch_settings_autosave_key_holds_only_the_steps_switch`
- `tests.test_ui_steps::test_the_rate_and_understand_switch_reads_as_designed`

### Node: import de i18n ausente

- `tests.test_job_progress::test_the_app_names_the_plugin_in_the_label_too`
- `tests.test_model_pull::test_the_percentage_never_reads_100_before_it_is_done`
- `tests.test_model_pull::test_the_checking_steps_say_to_keep_the_app_open`
- `tests.test_model_pull::test_the_engines_record_fills_in_what_the_events_missed`
- `tests.test_ui_campaigns::test_parse_link_sends_the_link_in_a_post_body_never_a_query_string`
- `tests.test_ui_campaigns::test_every_changing_call_sends_the_session_header_and_webhooks_go_in_bodies`
- `tests.test_ui_campaigns::test_reading_calls_send_no_header`
- `tests.test_ui_campaigns::test_without_the_desktop_app_nothing_that_changes_is_sent`
- `tests.test_ui_campaigns::test_the_cards_four_states_and_initials`
- `tests.test_ui_campaigns::test_an_edit_sends_only_what_changed_and_a_link_only_when_pasted`
- `tests.test_ui_gaming_layout_sync::test_the_preview_plans_every_case_like_the_render`
- `tests.test_ui_gaming_layout_sync::test_the_editors_copy_of_the_layout_table_is_the_same`
- `tests.test_ui_marketplace::test_categories_and_kinds_match_the_manifest`
- `tests.test_ui_marketplace::test_every_tier_and_execution_gets_a_badge_in_the_engines_words`
- `tests.test_ui_marketplace::test_install_asks_for_what_the_plugin_is_and_does`
- `tests.test_ui_marketplace::test_an_update_lists_new_permissions_hosts_and_data_leaving`
- `tests.test_ui_marketplace::test_hardware_fit[req0-hw0-expected0]`
- `tests.test_ui_marketplace::test_hardware_fit[req1-hw1-expected1]`
- `tests.test_ui_marketplace::test_hardware_fit[req2-hw2-expected2]`
- `tests.test_ui_marketplace::test_hardware_fit[req3-None-expected3]`
- `tests.test_ui_marketplace::test_hardware_fit[req4-hw4-expected4]`
- `tests.test_ui_marketplace::test_hardware_fit[req5-hw5-expected5]`
- `tests.test_ui_marketplace::test_hardware_fit[req6-hw6-expected6]`
- `tests.test_ui_marketplace::test_hardware_fit[req7-hw7-expected7]`
- `tests.test_ui_marketplace::test_hardware_fit[req8-None-expected8]`
- `tests.test_ui_marketplace::test_hardware_fit[req9-None-expected9]`
- `tests.test_ui_marketplace::test_python_and_the_engines_problems_join_the_needs`
- `tests.test_ui_marketplace::test_the_card_summary_never_says_it_fits_when_something_is_unknown`
- `tests.test_ui_marketplace::test_only_plain_https_links_are_offered_each_once`
- `tests.test_ui_marketplace::test_only_the_checks_the_index_build_runs_are_shown_and_a_failed_one_stays`
- `tests.test_ui_marketplace::test_only_pipelines_that_can_run_are_offered`
- `tests.test_ui_marketplace::test_only_pipelines_that_find_are_offered_as_pipeline`
- `tests.test_ui_marketplace::test_plugins_without_outputs_count_as_finders`
- `tests.test_ui_marketplace::test_update_lines_say_what_a_plugin_now_also_does`
- `tests.test_ui_marketplace::test_each_step_pill_says_where_it_is_chosen`
- `tests.test_ui_marketplace::test_an_editor_shows_suggests_edits`
- `tests.test_ui_marketplace::test_a_setting_is_refused_exactly_when_the_engine_would_refuse_it`
- `tests.test_ui_marketplace::test_text_that_is_not_a_number_is_refused`
- `tests.test_ui_marketplace::test_only_settings_changed_from_their_defaults_go_in_the_job`
- `tests.test_ui_marketplace::test_a_saved_choice_keeps_only_settings_the_installed_version_accepts`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[https://github.com/example-dev/example-plugin-0123456789abcdef0123456789abcdef01234567--expected0]`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[https://github.com/example-dev/monorepo/tree/0123456789abcdef0123456789abcdef01234567/plugins/demo---expected1]`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[https://github.com/example-dev/example-plugin.git-0123456789ABCDEF0123456789ABCDEF01234567-/sub/-expected2]`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[https://git.example.org/team/plugin-0123456789abcdef0123456789abcdef01234567--expected3]`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[-https://github.com/example-dev/monorepo/tree/0123456789abcdef0123456789abcdef01234567/plugins/demo--expected4]`
- `tests.test_ui_marketplace::test_a_pasted_link_becomes_a_source_the_engine_accepts[https://github.com/example-dev/monorepo-https://www.github.com/example-dev/monorepo/commit/0123456789abcdef0123456789abcdef01234567-x-expected5]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin-main--40-character commit]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin-0123456--40-character commit]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/x/tree/0123456789abcdef0123456789abcdef01234567-ffffffffffffffffffffffffffffffffffffffff--different commits]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[http://github.com/example-dev/example-plugin-0123456789abcdef0123456789abcdef01234567--https://]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[git@github.com:example-dev/example-plugin.git-0123456789abcdef0123456789abcdef01234567--https://]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin-0123456789abcdef0123456789abcdef01234567-../outside-a path inside the repository]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin/tree/main/plugins/demo---a branch or tag]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin-https://github.com/example-dev/example-plugin--40-character commit]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/a-https://github.com/example-dev/b/tree/0123456789abcdef0123456789abcdef01234567--different repositories]`
- `tests.test_ui_marketplace::test_a_link_the_engine_would_refuse_is_explained_first[https://github.com/example-dev/example-plugin/pulls-0123456789abcdef0123456789abcdef01234567--isn\u2019t a repository]`
- `tests.test_ui_marketplace::test_index_ages_sizes_and_slugs_read_as_words`
- `tests.test_ui_marketplace::test_clips_kittys_online_list_is_named_and_described_plainly`
- `tests.test_ui_marketplace::test_the_directory_kinds_and_relationships_match_the_catalog`
- `tests.test_ui_marketplace::test_badges_say_what_they_mean_and_a_listing_shows_only_the_extra_ones`
- `tests.test_ui_marketplace::test_an_official_listing_needs_no_trust_tick_and_a_community_one_does`
- `tests.test_ui_marketplace::test_each_number_is_its_own_line`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source0-https://github.com/example-org/app]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source1-https://github.com/example-org/app/tree/HEAD/tools/cli]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source2-https://github.com/example-org/app#readme]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source3-https://github.com/example-org/app]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source4-https://huggingface.co/example-org/speech]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source5-None]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source6-https://example.org/]`
- `tests.test_ui_marketplace::test_an_entry_links_to_its_home[source7-None]`
- `tests.test_ui_marketplace::test_an_entry_has_one_button_and_its_download_page_comes_first`
- `tests.test_ui_marketplace::test_credits_and_compatibility_in_words`
- `tests.test_ui_marketplace::test_entries_are_grouped_in_the_catalogs_order`
- `tests.test_ui_marketplace::test_version_ranges_read_as_words_the_way_the_engine_reads_them`
- `tests.test_ui_marketplace::test_where_a_listing_and_an_install_come_from_in_a_few_words`
- `tests.test_ui_marketplace::test_the_words_a_creator_reads_are_plain`
- `tests.test_ui_marketplace::test_the_consent_and_safety_lines_are_in_every_language`
- `tests.test_ui_sport_crop::test_full_screen_is_kept_only_where_it_is_offered_and_the_default_is_not_written`
- `tests.test_ui_sport_crop::test_the_crop_is_remembered_for_the_next_video_and_named_on_the_queue_chip`

### Encerramento dos vídeos (outro)

- `tests.test_outro::test_mascot_files_still_regenerate_identically`
- `tests.test_outro::test_shipped_settings_yaml_has_the_key`
- `tests.test_outro::test_append_does_not_re_encode_the_clip`
- `tests.test_outro::test_a_broken_outro_never_costs_the_clip`
- `tests.test_outro::test_a_truly_unwritable_clip_is_left_alone`
- `tests.test_outro::test_an_unshipped_format_still_works`
- `tests.test_outro::test_backfill_adds_only_what_is_missing`
- `tests.test_outro::test_a_relative_clip_path_still_works`
- `tests.test_outro::test_end_card_lands_even_while_the_app_previews_the_clip`
- `tests.test_outro::test_uncontended_clips_still_use_the_atomic_rename`
- `tests.test_outro::test_append_starts_the_video_at_0[ultrafast]`
- `tests.test_outro::test_append_starts_the_video_at_0[veryfast]`

### SDK, comandos Python e tutorial

- `tests.test_plugin_docs::test_the_tutorial_runs_as_written`
- `tests.test_plugin_sdk_new::test_new_prints_the_python_that_is_running`
- `tests.test_plugin_sdk_new::test_new_refuses_a_full_folder_and_the_reserved_publisher`

### Legendas de segunda voz / marcador ASS q2

- `tests.test_second_speaker_render::test_a_saved_post_style_is_ignored_and_the_second_colour_still_burns`
- `tests.test_second_speaker_render::test_a_clip_saved_with_the_highlights_post_style_renders_in_its_own_style`
- `tests.test_second_speaker_render::test_the_other_speakers_lines_burn_in_the_second_colour_and_the_turns_are_saved`
- `tests.test_second_speaker_render::test_a_clips_own_style_turns_it_on_for_that_clip`
- `tests.test_second_speaker_render::test_lines_the_user_saved_keep_their_words_and_take_the_colour`
- `tests.test_second_speaker_render::test_a_piece_sent_by_another_pc_uses_the_turns_that_came_with_it`
- `tests.test_second_speaker_render::test_a_hand_fix_colours_a_clip_the_render_heard_nobody_else_in`
- `tests.test_second_speaker_render::test_a_hand_fix_overrules_what_was_heard_and_what_was_heard_is_saved_as_heard`
- `tests.test_second_speaker_render::test_a_mark_left_on_a_saved_line_colours_nothing_when_nobody_else_is_heard`
- `tests.test_second_speaker_render::test_lines_the_editor_sends_with_a_fix_burn_as_the_editor_showed_them`
- `tests.test_second_speaker_render::test_a_hand_fix_marks_saved_lines_whole`
