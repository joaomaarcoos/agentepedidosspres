-- Reaplica correções com escapes Unicode para evitar corrupção no caminho cliente/SQL.

UPDATE produtos
SET filial = U&'Ribeir\00E3o Preto',
    nome = fixes.nome,
    updated_at = now()
FROM (
  VALUES
    ('SGRSSABH', '900', U&'GARRAFA ABACAXI COM HORTEL\00C3'),
    ('SBSSABH',  '05L', U&'BOLSA ABACAXI COM HORTEL\00C3'),
    ('SBSSSABH', '05L', U&'BOLSA ABACAXI COM HORTEL\00C3'),
    ('SGRSSMAR', '900', U&'GARRAFA MARACUJ\00C1 900ML'),
    ('SGRSSMAR', '1L7', U&'GARRAFA MARACUJ\00C1 1,7L'),
    ('SGRSSMMA', '300', U&'SUCO GARRAFA MANGA E MARACUJ\00C1'),
    ('SGRSSMMA', '900', U&'SUCO GARRAFA MANGA E MARACUJ\00C1'),
    ('SGPSSMMA', '05L', U&'GAL\00C3O MANGA E MARACUJ\00C1 05L')
) AS fixes(cod_produto, derivacao, nome)
WHERE produtos.cod_produto = fixes.cod_produto
  AND produtos.derivacao = fixes.derivacao;

UPDATE produtos
SET filial = U&'Ribeir\00E3o Preto',
    updated_at = now()
WHERE filial <> U&'Ribeir\00E3o Preto';

UPDATE tabelas_preco_itens t
SET nome_produto = p.nome,
    synced_at = now()
FROM produtos p
WHERE t.cod_produto = p.cod_produto
  AND COALESCE(t.variacao, '') = COALESCE(p.derivacao, '')
  AND t.nome_produto IS DISTINCT FROM p.nome;
