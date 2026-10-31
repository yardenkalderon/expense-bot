-- קישורי כניסה אישיים לדשבורד ("זכור את המכשיר").
-- הבוט יוצר שורה ב-/dashboard, הדשבורד בודק אותה כשהכתובת מכילה ?t=<token>.
-- נשמר רק hash של הטוקן. RLS מופעל בלי policies, כמו בשאר הטבלאות (גישה רק עם sb_secret_).

create table if not exists public.dashboard_sessions (
    id           bigint generated always as identity primary key,
    user_id      bigint      not null references public.authorized_users(user_id) on delete cascade,
    token_hash   text        not null unique,
    label        text,
    created_at   timestamptz not null default now(),
    last_used_at timestamptz not null default now(),
    expires_at   timestamptz not null
);

create index if not exists dashboard_sessions_user_id_idx on public.dashboard_sessions (user_id);

alter table public.dashboard_sessions enable row level security;
