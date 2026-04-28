-- schema.sql
-- Run this in your Supabase SQL editor (supabase.com → project → SQL Editor)

-- Users table
create table if not exists users (
  id            uuid default gen_random_uuid() primary key,
  email         text unique not null,
  business_name text,
  industry      text default 'General',
  plan          text default 'trial',        -- trial | pro
  active        boolean default true,
  report_day    text default 'monday',
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- OAuth tokens (one row per user per provider)
create table if not exists oauth_tokens (
  id           uuid default gen_random_uuid() primary key,
  user_email   text not null,
  provider     text not null,               -- xero | quickbooks
  token_data   text not null,               -- JSON blob (encrypted at rest by Supabase)
  updated_at   timestamptz default now(),
  unique (user_email, provider)
);

-- Report history
create table if not exists reports (
  id           uuid default gen_random_uuid() primary key,
  user_email   text not null,
  period       text not null,               -- e.g. "2026-04"
  summary      text not null,               -- JSON
  insights     text not null,               -- JSON
  generated_at timestamptz default now()
);

-- Row-level security: each user only sees their own rows
alter table users enable row level security;
alter table oauth_tokens enable row level security;
alter table reports enable row level security;

-- Allow service role (your backend) to read/write everything
create policy "service_full_access" on users
  using (true) with check (true);
create policy "service_full_access" on oauth_tokens
  using (true) with check (true);
create policy "service_full_access" on reports
  using (true) with check (true);

-- Indexes for common queries
create index if not exists idx_tokens_email_provider on oauth_tokens(user_email, provider);
create index if not exists idx_reports_email on reports(user_email);
create index if not exists idx_users_active on users(active) where active = true;
