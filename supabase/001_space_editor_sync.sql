-- Commercial Kitchen Space Editor: private project sharing and sync.
-- Run this whole file once in Supabase Dashboard > SQL Editor > New query.
-- Tables remain inaccessible to browser clients; access is only through the
-- three RPC functions below, using unguessable read/edit UUID capabilities.

create extension if not exists pgcrypto;

create table if not exists public.space_editor_projects (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 100),
  snapshot jsonb not null default '{}'::jsonb,
  edit_token uuid not null unique default gen_random_uuid(),
  view_token uuid not null unique default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.space_editor_projects enable row level security;
revoke all on table public.space_editor_projects from anon, authenticated;

create or replace function public.space_editor_create_project(
  p_name text,
  p_snapshot jsonb default '{}'::jsonb
)
returns table(project_id uuid, edit_secret uuid, view_secret uuid)
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.space_editor_projects (name, snapshot)
  values (
    left(coalesce(nullif(trim(p_name), ''), '未命名项目'), 100),
    coalesce(p_snapshot, '{}'::jsonb)
  )
  returning id, edit_token, view_token
  into project_id, edit_secret, view_secret;
  return next;
end;
$$;

create or replace function public.space_editor_read_project(
  p_project_id uuid,
  p_secret uuid
)
returns table(project_name text, project_snapshot jsonb, can_edit boolean, saved_at timestamptz)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  select p.name, p.snapshot, p.edit_token = p_secret, p.updated_at
  from public.space_editor_projects p
  where p.id = p_project_id
    and p_secret in (p.edit_token, p.view_token);
  if not found then
    raise exception 'Project link is invalid or has been revoked' using errcode = '42501';
  end if;
end;
$$;

create or replace function public.space_editor_write_project(
  p_project_id uuid,
  p_edit_secret uuid,
  p_snapshot jsonb
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.space_editor_projects
  set snapshot = coalesce(p_snapshot, '{}'::jsonb), updated_at = now()
  where id = p_project_id and edit_token = p_edit_secret;
  if not found then
    raise exception 'Edit link is invalid or has been revoked' using errcode = '42501';
  end if;
  return true;
end;
$$;

revoke all on function public.space_editor_create_project(text, jsonb) from public;
revoke all on function public.space_editor_read_project(uuid, uuid) from public;
revoke all on function public.space_editor_write_project(uuid, uuid, jsonb) from public;
grant execute on function public.space_editor_create_project(text, jsonb) to anon, authenticated;
grant execute on function public.space_editor_read_project(uuid, uuid) to anon, authenticated;
grant execute on function public.space_editor_write_project(uuid, uuid, jsonb) to anon, authenticated;
