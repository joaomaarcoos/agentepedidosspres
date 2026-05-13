create table if not exists public.ai_conversations (
  id uuid primary key default gen_random_uuid(),
  conversation_key text not null unique,
  phone text,
  ai_paused boolean not null default false,
  paused_at timestamptz,
  paused_until timestamptz,
  pause_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ai_conversation_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.ai_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'event')),
  content text not null default '',
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_ai_conversations_phone
  on public.ai_conversations(phone);

create index if not exists idx_ai_messages_conversation_created
  on public.ai_conversation_messages(conversation_id, created_at desc);
