-- Run this in Supabase Dashboard → SQL Editor to create tables and seed 10 user profiles.
-- Optional: the app works with built-in profiles if these tables don't exist.

-- User profiles (for frontend profile selector)
create table if not exists public.user_profiles (
  id text primary key,
  name text not null,
  level text not null,
  goals text,
  age_group text
);

-- Proficiency cache (updated by UserEvaluation agent)
create table if not exists public.proficiency (
  user_id text primary key,
  level text,
  updated_at timestamptz default now(),
  data jsonb
);

-- Seed 10 profiles (run once)
insert into public.user_profiles (id, name, level, goals, age_group) values
  ('1', 'Alex', 'A2', 'gaming, streaming', '18-25'),
  ('2', 'Maria', 'B1', 'travel, TikTok', '25-35'),
  ('3', 'Jordan', 'B2', 'work meetings, slang', '30-40'),
  ('4', 'Sam', 'A1', 'basics, memes', '16-22'),
  ('5', 'Casey', 'C1', 'native-like informal', '28-35'),
  ('6', 'Riley', 'A2', 'dating app, friends', '20-28'),
  ('7', 'Taylor', 'B1', 'podcasts, Reddit', '22-30'),
  ('8', 'Morgan', 'B2', 'gaming voice chat', '18-26'),
  ('9', 'Quinn', 'A2', 'travel, casual chat', '25-35'),
  ('10', 'Jamie', 'B1', 'social media, slang', '19-27')
on conflict (id) do nothing;
