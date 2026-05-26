-- =============================================================
-- Auth Migration: user_profiles
-- Rodar no Supabase SQL Editor (Dashboard > SQL Editor)
-- =============================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('master_dev', 'admin', 'gestor', 'representante')),
  cod_rep     INTEGER,
  cpf         TEXT,
  nome        TEXT NOT NULL,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Usuário lê seu próprio perfil
CREATE POLICY "user_profiles: self read"
  ON public.user_profiles FOR SELECT
  USING (auth.uid() = id);

-- Evita recursao nas policies que precisam consultar a propria user_profiles
CREATE OR REPLACE FUNCTION public.current_user_is_admin()
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_profiles p
    WHERE p.id = auth.uid()
      AND p.role IN ('master_dev', 'admin')
      AND p.ativo = TRUE
  );
$$;

GRANT EXECUTE ON FUNCTION public.current_user_is_admin() TO authenticated;

-- master_dev e admin leem todos os perfis
CREATE POLICY "user_profiles: admin read all"
  ON public.user_profiles FOR SELECT
  USING (public.current_user_is_admin());

-- master_dev e admin gerenciam todos os perfis
CREATE POLICY "user_profiles: admin write"
  ON public.user_profiles FOR ALL
  USING (public.current_user_is_admin())
  WITH CHECK (public.current_user_is_admin());

-- Usuário atualiza seu próprio perfil (nome, cpf, cod_rep)
CREATE POLICY "user_profiles: self update"
  ON public.user_profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Auto-atualiza updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER user_profiles_updated_at
  BEFORE UPDATE ON public.user_profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =============================================================
-- BOOTSTRAP: Após criar o primeiro usuário no Supabase Auth,
-- execute com o UUID gerado:
-- =============================================================
-- INSERT INTO public.user_profiles (id, role, nome)
-- VALUES ('<uuid-do-usuario>', 'master_dev', 'Dev Master');
