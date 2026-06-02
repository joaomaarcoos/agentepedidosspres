-- Pedidos criados/editados pela IA devem aguardar aprovacao no sistema.
-- Qualquer pedido ainda em revisao volta para pendente.

UPDATE pedidos_revisao
SET status = 'pendente',
    revisado_em = NULL,
    updated_at = now()
WHERE status = 'em_revisao';
