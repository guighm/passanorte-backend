# Issues — Serviço de Insights

Cada issue corresponde a um endpoint do serviço. Referências: RF06–RF10, RNF08. Todos exigem papel `admin`; as agregações são 100% SQL sobre o banco próprio (Princípio I).

| Título | Descrição |
|---|---|
| `GET /heatmap` — mapa de calor de visitas | Concentração de visitas por ponto turístico (RF06): contagem, coordenadas e `weight = count / total` por `GROUP BY tourist_spot_id` sobre `visit_facts` (sem filtro temporal). Nota: `total` é o número de pontos distintos, não o total de visitas. |
| `GET /accesses` — acessos por período | Acessos à plataforma agrupados por período (RF07): `period` = `day\|week\|month\|year\|custom` (default `day`); `custom` exige `from`/`to` em ISO, senão 422 `invalid_period`. Alimentado pelo consumo de `access.registered`. |
| `GET /rankings/tourist-spots` — pontos mais visitados | Ranking de pontos turísticos por visitas (RF08), com `segment` = `day\|month\|year` (default `month`). |
| `GET /distributions/country-of-origin` — distribuição por país | Participação de visitas/países de origem (RF09), a partir do snapshot sem PII dos fatos (RNF08). |
| `GET /distributions/interests` — distribuição por interesse | Participação por interesse do turista (RF10). Agrega em Python: split do CSV de interesses por fato e dedup por `set`. |