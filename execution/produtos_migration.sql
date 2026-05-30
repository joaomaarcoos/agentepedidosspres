-- Migration: create_produtos_table
-- Rodar uma vez no Supabase (Dashboard > SQL Editor) ou via supabase db push

CREATE TABLE IF NOT EXISTS produtos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filial text NOT NULL DEFAULT 'Ribeirao Preto',
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

-- Dados: Ribeirao Preto
INSERT INTO produtos (filial, cod_produto, nome, derivacao, preco_base, preco_inst_299) VALUES
  -- Garrafas 300ml
  ('Ribeirao Preto', 'SGRSSCAJ', 'GARRAFA CAJU 300 ML',             '300', 3.10, 3.22),
  ('Ribeirao Preto', 'SGRSSMMA', 'SUCO GARRAFA MANGA E MARACUJA',   '300', 3.85, 3.97),
  ('Ribeirao Preto', 'SGRSSLAR', 'GARRAFA LARANJA 300ML',           '300', 3.89, 4.07),
  -- Garrafas 900ml
  ('Ribeirao Preto', 'SGRSSABH', 'GARRAFA ABACAXI COM HORTELA',     '900', 7.75, 8.01),
  ('Ribeirao Preto', 'SGRSSCAJ', 'GARRAFA CAJU 900ML',              '900', 6.66, 6.92),
  ('Ribeirao Preto', 'SGRSSCOC', 'GARRAFA AGUA DE COCO',            '900', 10.20, 11.20),
  ('Ribeirao Preto', 'SGRSSGOI', 'GARRAFA GOIABA 900ML',            '900', 6.66, 6.92),
  ('Ribeirao Preto', 'SGRSSLAR', 'GARRAFA LARANJA 900ML',           '900', 9.17, 9.44),
  ('Ribeirao Preto', 'SGRSSLMO', 'GARRAFA LARANJA C/ MORANGO 900ML','900', 10.78, 11.07),
  ('Ribeirao Preto', 'SGRSSMAR', 'GARRAFA MARACUJA 900ML',          '900', 8.80, 9.08),
  ('Ribeirao Preto', 'SGRSSMMA', 'SUCO GARRAFA MANGA E MARACUJA',   '900', 7.90, 8.06),
  -- Garrafas 1,7L
  ('Ribeirao Preto', 'SGRSSCAJ', 'GARRAFA CAJU 1,7 L',              '1L7', 11.70, 12.43),
  ('Ribeirao Preto', 'SGRSSLAR', 'GARRAFA LARANJA 1,7 L',           '1L7', 16.26, 16.98),
  ('Ribeirao Preto', 'SGRSSMAR', 'GARRAFA MARACUJA 1,7L',           '1L7', 16.72, 17.49),
  ('Ribeirao Preto', 'SGRSSUVA', 'GARRAFA UVA 1,7L',                '1L7', 15.81, 16.74),
  -- Copos 200ml
  ('Ribeirao Preto', 'SCPSSCAJ', 'COPO CAJU 200ML',                 '200', 1.55, 1.61),
  ('Ribeirao Preto', 'SCPSSGOI', 'COPO GOIABA 200ML',               '200', 1.55, 1.61),
  ('Ribeirao Preto', 'SCPSSLAR', 'COPO LARANJA 200ML',              '200', 2.06, 2.06),
  ('Ribeirao Preto', 'SCPSSMAR', 'COPO MARACUJA 200ML',             '200', 1.80, 1.98),
  ('Ribeirao Preto', 'SCPSSUVA', 'COPO UVA 200ML',                  '200', 2.10, 2.18),
  -- Copos 115ml
  ('Ribeirao Preto', 'SCPSSLAR', 'COPO LARANJA 115ML',              '115', 1.23, 1.23),
  ('Ribeirao Preto', 'SCPSSMAC', 'SUCO COPO MACA 115ML',            '115', 1.27, 1.27),
  -- Bolsas 5L
  ('Ribeirao Preto', 'CBSSSLAR', 'BOLSA LARANJA CONCENTRADO 5L',    '05L', 38.06, 38.06),
  ('Ribeirao Preto', 'SBSSABH',  'BOLSA ABACAXI COM HORTELA',       '05L', 30.40, 31.62),
  ('Ribeirao Preto', 'SBSSSABH', 'BOLSA ABACAXI COM HORTELA',       '05L', 33.80, 35.78),
  ('Ribeirao Preto', 'SBSSSCAJ', 'BOLSA CAJU 5L',                   '05L', 25.20, 26.21),
  ('Ribeirao Preto', 'SBSSSCLA', 'BOLSA LARANJA COMPOSTO 5L',       '05L', 27.10, 27.10),
  ('Ribeirao Preto', 'SBSSSGOI', 'BOLSA GOIABA 5L',                 '05L', 24.20, 25.17),
  ('Ribeirao Preto', 'SBSSSLAR', 'BOLSA LARANJA INTEGRAL 5L',       '05L', 37.10, 37.10),
  ('Ribeirao Preto', 'SBSSSMAR', 'BOLSA MARACUJA 5L',               '05L', 33.00, 36.30),
  ('Ribeirao Preto', 'SBSSSUVA', 'BOLSA UVA 5L',                    '05L', 33.00, 34.32),
  -- Galoes 5L
  ('Ribeirao Preto', 'SGPSSCLA', 'GALAO LARANJA COMPOSTO 05L',      '05L', 28.89, 28.89),
  ('Ribeirao Preto', 'SGPSSLAR', 'GALAO LARANJA 5L',                '05L', 38.80, 38.80),
  ('Ribeirao Preto', 'SGPSSMMA', 'GALAO MANGA E MARACUJA 05L',      '05L', 38.50, 39.66),
  ('Ribeirao Preto', 'SGPSSUVA', 'GALAO UVA 5L',                    '05L', 33.00, 34.32)
ON CONFLICT (cod_produto, derivacao) DO UPDATE
  SET nome           = EXCLUDED.nome,
      preco_base     = EXCLUDED.preco_base,
      preco_inst_299 = EXCLUDED.preco_inst_299,
      updated_at     = now();
