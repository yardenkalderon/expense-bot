-- Category change (Nov 2026): split "חשבונות ובית", add "מנויים", insurance under health.
-- Run right after deploying the code that has the new CATEGORIES list. Safe to run twice.

-- Backup in a schema that PostgREST does not expose
create schema if not exists backup;
create table if not exists backup.expenses_2026_11 as table public.expenses;
create table if not exists backup.recurring_expenses_2026_11 as table public.recurring_expenses;
create table if not exists backup.budgets_2026_11 as table public.budgets;

-- Renames
update public.expenses           set category = 'דיור וחשבונות' where category = 'חשבונות ובית';
update public.recurring_expenses set category = 'דיור וחשבונות' where category = 'חשבונות ובית';
update public.budgets            set category = 'דיור וחשבונות' where category = 'חשבונות ובית';
update public.expenses           set category = 'בריאות וביטוח' where category = 'בריאות';
update public.recurring_expenses set category = 'בריאות וביטוח' where category = 'בריאות';
update public.budgets            set category = 'בריאות וביטוח' where category = 'בריאות';

-- Subscriptions
update public.expenses set category = 'מנויים'
 where item in ('נטפליקס', 'אפל', 'פרטנר וויפי', 'ANTHROPIC', 'אפליקציה ללימודים');
update public.recurring_expenses set category = 'מנויים'
 where item in ('נטפליקס', 'אפל', 'פרטנר וויפי');

-- Insurance
update public.expenses set category = 'בריאות וביטוח' where item like '%ביטוח%';
update public.recurring_expenses set category = 'בריאות וביטוח' where item like '%ביטוח%';

-- Household goods are shopping, not housing
update public.expenses set category = 'קניות וסופר'
 where item in ('שידה לחדר שינה', 'מצעים לדירה', 'חומרי ניקוי', 'ספריי למזגן');

-- Small fixes
update public.expenses set category = 'אחר' where item = 'פרחים' and category = 'דיור וחשבונות';
update public.expenses set category = 'תחבורה ודלק' where item = 'גלגל קורקינט';
