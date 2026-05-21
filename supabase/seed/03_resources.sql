-- supabase/seed/03_resources.sql
-- UKP Resources Registry — seed data

insert into resources_registry (uri_pattern, name, description, mime_type, category, is_dynamic) values
('vault://notes/{path}', 'Note individuelle', 'Contenu complet d''une note par chemin Obsidian', 'text/markdown', 'note', true),
('vault://projects/{slug}', 'Notes par projet', 'Lister les notes d''un projet/section', 'application/json', 'project', true),
('vault://sections/{slug}', 'Section complète', 'Contenu et métadonnées d''une section', 'application/json', 'section', true),
('vault://session/current', 'Session active', 'Session en cours', 'application/json', 'session', true),
('vault://memory/{project}', 'Mémoire projet', 'Mémoires persistantes', 'application/json', 'memory', true),
('vault://profile/current', 'Profil actif', 'Profil de contexte chargé', 'application/json', 'profile', true)
on conflict (uri_pattern) do nothing;
