-- Migration: create_produtos_table
-- Rodar uma vez no Supabase (Dashboard > SQL Editor) ou via supabase db push

CREATE TABLE IF NOT EXISTS produtos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filial text NOT NULL DEFAULT 'Ribeirão Preto',
  cod_produto text NOT NULL,
  nome text NOT NULL,
  derivacao text NOT NULL DEFAULT '',
  preco_base numeric(10,2),
  preco_inst_299 numeric(10,2),
  ativo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS produtos_cod_derivacao_uidx ON produtos (cod_produto, derivacao);
CREATE INDEX IF NOT EXISTS produtos_ativo_idx ON produtos (ativo);

CREATE OR REPLACE FUNCTION update_produtos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS produtos_updated_at_trigger ON produtos;
CREATE TRIGGER produtos_updated_at_trigger
  BEFORE UPDATE ON produtos
  FOR EACH ROW EXECUTE FUNCTION update_produtos_updated_at();

-- Dados: Ribeirão Preto
INSERT INTO produtos (filial, cod_produto, nome, derivacao, preco_base, preco_inst_299) VALUES
  -- Garrafas 300ml
  ('Ribeirão Preto', 'SGRSSCAJ', 'GARRAFA CAJU 300 ML',            '300', 3.10, 3.22),
  ('Ribeirão Preto', 'SGRSSMMA', 'SUCO GARRAFA MANGA E MARACUJÁ',  '300', 3.85, 3.97),
  -- Copos 200ml
  ('Ribeirão Preto', 'SCPSSCAJ', 'COPO CAJU 200ML',                '200', 1.55, 1.61),
  ('Ribeirão Preto', 'SCPSSGOI', 'COPO GOIABA 200ML',              '200', 1.55, 1.61),
  ('Ribeirão Preto', 'SCPSSLAR', 'COPO LARANJA 200ML',             '200', 2.06, 2.06),
  ('Ribeirão Preto', 'SCPSSMAR', 'COPO MARACUJÁ 200ML',            '200', 1.80, 1.98),
  ('Ribeirão Preto', 'SCPSSUVA', 'COPO UVA 200ML',                 '200', 2.10, 2.18),
  -- Copos 115ml
  ('Ribeirão Preto', 'SCPSSLAR', 'COPO LARANJA 115ML',             '115', 1.23, 1.23),
  ('Ribeirão Preto', 'SCPSSMAC', 'SUCO COPO MAÇÃ 115ML',           '115', 1.27, 1.27),
  -- Bolsas 5L
  ('Ribeirão Preto', 'CBSSSLAR', 'BOLSA LARANJA CONCENTRADO 5L',   '05L', 38.06, 38.06),
  ('Ribeirão Preto', 'SBSSABH',  'BOLSA ABACAXI COM HORTELÃ',      '05L', 30.40, 31.62),
  ('Ribeirão Preto', 'SBSSSCAJ', 'BOLSA CAJU 5L',                  '05L', 25.20, 26.21),
  ('Ribeirão Preto', 'SBSSSCLA', 'BOLSA LARANJA COMPOSTO 5L',      '05L', 27.10, 27.10),
  ('Ribeirão Preto', 'SBSSSGOI', 'BOLSA GOIABA 5L',                '05L', 24.20, 25.17),
  ('Ribeirão Preto', 'SBSSSLAR', 'BOLSA LARANJA INTEGRAL 5L',      '05L', 37.10, 37.10),
  ('Ribeirão Preto', 'SBSSSMAR', 'BOLSA MARACUJÁ 5L',              '05L', 33.00, 36.30),
  ('Ribeirão Preto', 'SBSSSUVA', 'BOLSA UVA 5L',                   '05L', 33.00, 34.32),
  -- Galões 5L
  ('Ribeirão Preto', 'SGPSSCLA', 'GALÃO LARANJA COMPOSTO 05L',     '05L', 28.89, 28.89),
  ('Ribeirão Preto', 'SGPSSLAR', 'GALÃO LARANJA 5L',               '05L', 38.80, 38.80),
  ('Ribeirão Preto', 'SGPSSMMA', 'GALÃO MANGA E MARACUJÁ 05L',     '05L', 38.50, 39.66),
  ('Ribeirão Preto', 'SGPSSUVA', 'GALÃO UVA 5L',                   '05L', 33.00, 34.32)
ON CONFLICT (cod_produto, derivacao) DO UPDATE
  SET nome          = EXCLUDED.nome,
      preco_base    = EXCLUDED.preco_base,
      preco_inst_299 = EXCLUDED.preco_inst_299,
      updated_at    = now();
