import pyodbc
from utils import write_log

CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=primno4;"
    "Database=RobbysonMatriz;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

META_VARIACAO_IMPORT_MATRIZ = """
use robbysonmatriz

set nocount on

if object_id('tempdb..#ids_quebra_semanal') is not null drop table #ids_quebra_semanal;
if object_id('tempdb..#ti') is not null drop table #ti;
if object_id('tempdb..#ids_desconsiderar') is not null drop table #ids_desconsiderar;
if object_id('tempdb..#fi') is not null drop table #fi;
if object_id('tempdb..#limites_indicadores') is not null drop table #limites_indicadores;
if object_id('tempdb..#im') is not null drop table #im;
if object_id('tempdb..#formulas') is not null drop table #formulas;
if object_id('tempdb..#agg') is not null drop table #agg;
if object_id('tempdb..#base') is not null drop table #base;
if object_id('tempdb..#atingimento') is not null drop table #atingimento;

--- indicadores com quebra semanal ----

select
    atributo,
    id_indicador,
    count(id_indicador) as qtd
into #ids_quebra_semanal
from robbyson.rby.import_matriz (nolock)
where dateadd(d, 1, eomonth(data_inicio, -1)) = dateadd(d, 1, eomonth(getdate(), -2))
group by atributo, id_indicador
having count(id_indicador) > 1

-----------------

---- tipos indicadores ----

select 
    id_indicador,
    formula_meta,
    indicador_nome,
    case when formula_perc_atingimento like '%meta/resultado%' then 'menor melhor'
    when formula_perc_atingimento like '%resultado/meta%' then 'maior melhor'
    when formula_perc_atingimento is null then 'nenhum'
    else 'maior melhor' end as tipo
into #ti
from robbyson.rby.indicador (nolock)
where formula_perc_atingimento is not null

--------

---- ids desconsiderar ----

select *
into #ids_desconsiderar
from (values
    (6,'fixos'),
    (34,'fixos'),
    (15,'fixos'),
    (48,'fixos'),
    (49,'fixos')
) v(id_indicador, tipo_desconsiderar)
union all
select 
    id_indicador,
    'meta_mis' as tipo_desconsiderar
from #ti ti
where formula_meta not like '%fatorcalc%' and formula_meta not like '%meta%' and indicador_nome <> 'descontinuado'
union all
select distinct 
    id_indicador,
    'pausa' as tipo_desconsiderar
from #ti ti
where indicador_nome like '%pausa%'
union all
select distinct 
    id_indicador,
    'ids_tipo_horario' as tipo_desconsiderar
from robbyson.rby.indicador (nolock)
where tipo_medida_indicador = 'admin_generic_hour'

--------

---- formatos indicadores ----

select 
    id_indicador, 
    id_formato,
    case when 
        formato = 'coin' then 'integer' 
        else formato 
    end as formato 
into #fi
from robbyson.dbo.rby_indicador (nolock) 
where formato is not null

--------

---- import matriz ----

select 
    im.atributo, 
    im.id_indicador,
    case 
        when id_formato = 4 then cast(im.meta*86400 as decimal(10,2))
        else cast(im.meta as decimal(10,2))
    end as meta,
    case
        when im.id_indicador in (select id_indicador from robbyson.rby.indicador (nolock) where (indicador_nome like '%tmo%' or indicador_nome like '%tma%' or indicador_nome like '%tmt%' or indicador_nome like '%tmia%'))
            then 0
        else 1
    end as pode_facilitar,
    dateadd(d, 1, eomonth(im.data_inicio, -1)) as periodo
into #im
from robbyson.rby.import_matriz (nolock) im
left join #fi fi on fi.id_indicador = im.id_indicador
where dateadd(d, 1, eomonth(im.data_inicio, -1)) = dateadd(d, 1, eomonth(getdate(), -2)) 
and im.ativo > 0
and not exists (
    select 1 
    from #ids_desconsiderar d
    where d.id_indicador = im.id_indicador
)
create index ix_im on #im (id_indicador, atributo);

--------

---- atingimento e meta dos ultimos 3 meses fechados ----

select
    id_indicador,
    id_formula_resultado,
    id_formula_meta,
    id_formula_atingimento
into #formulas
from robbyson.dbo.rby_indicador (nolock)

SELECT
    id_indicador,
    segmento,
    SUM(resultado)  AS s_resultado,
    SUM(fator)      AS s_fator,
    SUM(fator_2)    AS s_fator2,
    SUM(fator_3)    AS s_fator3,
    SUM(fator_4)    AS s_fator4,
    SUM(meta)       AS s_meta,
    count(chave_externa)         AS s_hc

INTO #agg
FROM robbyson.rby.performance (NOLOCK)
WHERE data >= dateadd(d, 1, eomonth(getdate(), -4)) and data < dateadd(d, 1, eomonth(getdate(), -1))
AND id_indicador not in (select id_indicador from #ids_desconsiderar)
GROUP BY
    id_indicador,
    segmento

SELECT
    a.id_indicador,
    a.segmento,
    f.id_formula_atingimento,
    a.s_hc,

    CASE 
        WHEN id_formula_resultado = 2 THEN s_resultado
        WHEN id_formula_resultado = 3 THEN iif(s_fator = 0, 0, s_resultado / s_fator)
        WHEN id_formula_resultado = 5 THEN iif((s_fator = 0 or s_fator3 = 0), 0, (s_resultado / s_fator) - (s_fator2 / s_fator3))
        WHEN id_formula_resultado = 6 THEN iif(s_fator2 = 0, 0, s_resultado / s_fator2)
        WHEN id_formula_resultado = 7 THEN IIF(s_resultado = 0, 0, s_fator / s_resultado)
        WHEN id_formula_resultado = 8 THEN iif(s_fator = 0, 0, 1 - (s_resultado / s_fator))
        WHEN id_formula_resultado = 9 THEN iif((s_fator2 = 0 or s_fator3 = 0), 0, ((s_resultado / s_fator2) - (s_fator2 / s_fator3)) * 100)
        WHEN id_formula_resultado = 10 THEN iif((s_fator = 0 or s_fator3 = 0), 0, (s_resultado / s_fator) + (s_fator2 / s_fator3))
        WHEN id_formula_resultado = 11 THEN IIF((s_fator = 0 OR s_fator4 > s_fator or s_fator2 = 0),0,(s_resultado/(s_fator2/s_fator))*(1-(s_fator3/s_fator)))
        WHEN id_formula_resultado = 12 THEN iif(s_fator2 = 0, 0, (s_resultado - s_fator) / s_fator2)
        WHEN id_formula_resultado = 13 THEN iif(s_fator = 0, 0, (s_resultado / s_fator) - (s_fator2 / s_fator))
        when id_formula_resultado = 14 THEN s_fator - s_resultado
        when id_formula_resultado = 15 THEN iif((s_fator = 0 or s_fator3 = 0 or s_fator2 = 0), 0, (s_resultado / s_fator)/(s_fator2 / s_fator3))
    END AS resultado,

    CASE
        WHEN id_formula_meta = 1  THEN iif(s_hc = 0,0, s_meta / s_hc)
        WHEN id_formula_meta = 2  THEN iif(s_fator2 = 0,0,s_fator / s_fator2)
        WHEN id_formula_meta = 3  THEN s_fator4
        WHEN id_formula_meta = 4  THEN IIF(s_fator3 = 0,0,s_fator4 / s_fator3)
        WHEN id_formula_meta = 5  THEN IIF(s_hc = 0,0,s_meta / s_hc)
        WHEN id_formula_meta = 6  THEN s_fator2
        WHEN id_formula_meta = 7  THEN IIF(s_fator = 0,0,s_meta / s_fator)
        WHEN id_formula_meta = 8  THEN IIF(s_fator2 = 0,0,s_meta / s_fator2)
        WHEN id_formula_meta = 9  THEN IIF(s_fator4 = 0,0,s_meta / s_fator4)
        WHEN id_formula_meta = 10 THEN IIF(s_fator = 0,0,s_fator2 / s_fator)
        WHEN id_formula_meta = 11 THEN IIF(s_fator3 = 0,0,s_fator2 / s_fator3)
    END AS meta

INTO #base
FROM #agg a
left join #formulas f on a.id_indicador = f.id_indicador

SELECT DISTINCT
    segmento as atributo,
    b.id_indicador,
    resultado,
    case when
        fi.id_formato = 3 then meta * 100
    else meta end as meta,
    CASE 
        WHEN id_formula_atingimento = 2 THEN IIF(resultado = 0, 10, meta/resultado)
        WHEN id_formula_atingimento = 3 THEN IIF(meta = 0 OR resultado <= 0, 0, resultado/meta)
        WHEN id_formula_atingimento = 4 THEN IIF(resultado > meta, meta/resultado, resultado/meta)
        WHEN id_formula_atingimento = 6 THEN IIF(meta = -1, 0, (resultado+1)/(meta+1))
        WHEN id_formula_atingimento = 7 THEN IIF(meta > 0.00001, resultado/meta,IIF(resultado = 0, 1, resultado/meta))
        WHEN id_formula_atingimento = 8 THEN iif(meta = 0, 0, IIF(resultado/meta >= 1, 0, resultado/meta))
        WHEN id_formula_atingimento = 9 THEN IIF(resultado >= 0, 10, meta/resultado)
        when id_formula_atingimento = 10 THEN IIF(meta = 0, 0, IIF(resultado > meta, meta/resultado, resultado/meta))
        WHEN id_formula_atingimento = 11 THEN IIF((resultado = 0 OR meta = 0), 0, meta/resultado)
        ELSE NULL
    END AS atingimento
into #atingimento
FROM #base b
left join #fi fi
    on fi.id_indicador = b.id_indicador

--------

---- limites inferior e superior ----

select *
into #limites_indicadores
from (values
    (901,94,96.5)
) v(id_indicador, faixa_inferior, faixa_superior)

--------

---- query final ----
insert into dbo.meta_variacao_sistema_matriz
select distinct
    cast(getdate() as date) as data_insercao,
    im.periodo,
    im.atributo,
    im.id_indicador,
    ti.indicador_nome as nome_indicador,
    fi.formato as formato_indicador,
    ti.tipo as tipo_indicador,
    cast(atng.meta as decimal(10,2)) as meta,
    round(atng.atingimento, 2) as atingimento,
    f.fator,
    im.pode_facilitar,
    case 
        when lim.id_indicador is not null then
            case 
                when (atng.meta * f.fator) > lim.faixa_superior 
                    then cast(lim.faixa_superior as decimal(10,2))
                when (atng.meta * f.fator) < lim.faixa_inferior 
                    then cast(lim.faixa_inferior as decimal(10,2))
                else 
                    cast(round(
                        cast(atng.meta as decimal(18,2)) * f.fator
                    ,2) as decimal(10,2))
            end
        else 
            case 
                when fi.formato = 'integer' 
                    then cast(round(atng.meta * f.fator, 0) as decimal(10,2))
                else 
                    cast(round(
                        cast(atng.meta as decimal(18,2)) * f.fator
                    ,2) as decimal(10,2))
            end
    end as meta_variacao
from #im im
left join #ti ti
    on ti.id_indicador = im.id_indicador
left join #fi fi
    on fi.id_indicador = im.id_indicador
left join #atingimento atng
    on atng.atributo = im.atributo
   and atng.id_indicador = im.id_indicador
left join #limites_indicadores lim
    on lim.id_indicador = im.id_indicador
cross apply (
    select 
        cast(
            case 
                when isnull(atng.atingimento, 0) >= 1 then 
                    case 
                        when ti.tipo = 'maior melhor' then 1.015
                        else 0.985
                    end
                else 
                    case 
                        when im.pode_facilitar = 1 then 
                            case 
                                when ti.tipo = 'maior melhor' then 0.985
                                else 1.015
                            end
                        else 1.000
                    end
            end 
        as decimal(6,3)) as fator
) f
where atingimento is not null
and im.atributo not in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))
and not exists (
    select 1
    from #ids_quebra_semanal q
    where q.id_indicador = im.id_indicador
    and q.atributo = im.atributo
)


drop table #ti
drop table #ids_desconsiderar
drop table #fi
drop table #limites_indicadores
drop table #im
drop table #formulas
drop table #agg
drop table #base
drop table #atingimento
drop table #ids_quebra_semanal
"""

META_VARIACAO_SISTEMA_MATRIZ = """
use robbysonmatriz

set nocount on

if object_id('tempdb..#ids_quebra_semanal') is not null drop table #ids_quebra_semanal;
if object_id('tempdb..#ti') is not null drop table #ti;
if object_id('tempdb..#ids_desconsiderar') is not null drop table #ids_desconsiderar;
if object_id('tempdb..#fi') is not null drop table #fi;
if object_id('tempdb..#limites_indicadores') is not null drop table #limites_indicadores;
if object_id('tempdb..#sm') is not null drop table #sm;
if object_id('tempdb..#formulas') is not null drop table #formulas;
if object_id('tempdb..#agg') is not null drop table #agg;
if object_id('tempdb..#base') is not null drop table #base;
if object_id('tempdb..#atingimento') is not null drop table #atingimento;

--- indicadores com quebra semanal ----

select
    atributo,
    id_indicador,
    count(id_indicador) as qtd
into #ids_quebra_semanal
from robbysonmatriz.dbo.sistema_matriz (nolock)
where periodo = dateadd(d, 1, eomonth(getdate(), -2))
group by atributo, id_indicador
having count(id_indicador) > 1

-----------------

---- tipos indicadores ----

select 
    id_indicador,
    formula_meta,
    indicador_nome,
    case when formula_perc_atingimento like '%meta/resultado%' then 'menor melhor'
    when formula_perc_atingimento like '%resultado/meta%' then 'maior melhor'
    when formula_perc_atingimento is null then 'nenhum'
    else 'maior melhor' end as tipo
into #ti
from robbyson.rby.indicador (nolock)
where formula_perc_atingimento is not null

--------

---- ids desconsiderar ----

select *
into #ids_desconsiderar
from (values
    (6,'fixos'),
    (34,'fixos'),
    (15,'fixos'),
    (48,'fixos'),
    (49,'fixos')
) v(id_indicador, tipo_desconsiderar)
union all
select 
    id_indicador,
    'meta_mis' as tipo_desconsiderar
from #ti ti
where formula_meta not like '%fatorcalc%' and formula_meta not like '%meta%' and indicador_nome <> 'descontinuado'
union all
select distinct 
    id_indicador,
    'pausa' as tipo_desconsiderar
from #ti ti
where indicador_nome like '%pausa%'
union all
select distinct 
    id_indicador,
    'ids_tipo_horario' as tipo_desconsiderar
from robbyson.rby.indicador (nolock)
where tipo_medida_indicador = 'admin_generic_hour'

--------

---- formatos indicadores ----

select 
    id_indicador, 
    id_formato,
    case when 
        formato = 'coin' then 'integer' 
        else formato 
    end as formato 
into #fi
from robbyson.dbo.rby_indicador (nolock) 
where formato is not null

--------

---- sistema matriz ----

select 
    sm.atributo, 
    sm.id_indicador,
    case 
        when id_formato = 4 then cast(datediff(second,'00:00:00',try_cast(sm.meta_final as time)) as decimal(10,2))
        else cast(sm.meta_final as decimal(10,2))
    end as meta,
    case
        when sm.id_indicador in (select id_indicador from robbyson.rby.indicador (nolock) where (indicador_nome like '%tmo%' or indicador_nome like '%tma%' or indicador_nome like '%tmt%'  or indicador_nome like '%tmia%'))
            then 0
        else 1
    end as pode_facilitar,
    sm.periodo
into #sm
from robbysonmatriz.dbo.sistema_matriz (nolock) sm
left join #fi fi on fi.id_indicador = sm.id_indicador
where periodo = dateadd(d, 1, eomonth(getdate(), -1)) 
and not exists (
    select 1 
    from #ids_desconsiderar d
    where d.id_indicador = sm.id_indicador
)
create index ix_sm on #sm (id_indicador, atributo);

--------

---- atingimento e meta dos ultimos 3 meses fechados ----

select
    id_indicador,
    id_formula_resultado,
    id_formula_meta,
    id_formula_atingimento
into #formulas
from robbyson.dbo.rby_indicador (nolock)

SELECT
    id_indicador,
    segmento,
    SUM(resultado)  AS s_resultado,
    SUM(fator)      AS s_fator,
    SUM(fator_2)    AS s_fator2,
    SUM(fator_3)    AS s_fator3,
    SUM(fator_4)    AS s_fator4,
    SUM(meta)       AS s_meta,
    count(chave_externa)         AS s_hc

INTO #agg
FROM robbyson.rby.performance (NOLOCK)
WHERE data >= dateadd(d, 1, eomonth(getdate(), -4)) and data < dateadd(d, 1, eomonth(getdate(), -1))
AND id_indicador not in (select id_indicador from #ids_desconsiderar)
GROUP BY
    id_indicador,
    segmento

SELECT
    a.id_indicador,
    a.segmento,
    f.id_formula_atingimento,
    a.s_hc,

    CASE 
        WHEN id_formula_resultado = 2 THEN s_resultado
        WHEN id_formula_resultado = 3 THEN iif(s_fator = 0, 0, s_resultado / s_fator)
        WHEN id_formula_resultado = 5 THEN iif((s_fator = 0 or s_fator3 = 0), 0, (s_resultado / s_fator) - (s_fator2 / s_fator3))
        WHEN id_formula_resultado = 6 THEN iif(s_fator2 = 0, 0, s_resultado / s_fator2)
        WHEN id_formula_resultado = 7 THEN IIF(s_resultado = 0, 0, s_fator / s_resultado)
        WHEN id_formula_resultado = 8 THEN iif(s_fator = 0, 0, 1 - (s_resultado / s_fator))
        WHEN id_formula_resultado = 9 THEN iif((s_fator2 = 0 or s_fator3 = 0), 0, ((s_resultado / s_fator2) - (s_fator2 / s_fator3)) * 100)
        WHEN id_formula_resultado = 10 THEN iif((s_fator = 0 or s_fator3 = 0), 0, (s_resultado / s_fator) + (s_fator2 / s_fator3))
        WHEN id_formula_resultado = 11 THEN IIF((s_fator = 0 OR s_fator4 > s_fator or s_fator2 = 0),0,(s_resultado/(s_fator2/s_fator))*(1-(s_fator3/s_fator)))
        WHEN id_formula_resultado = 12 THEN iif(s_fator2 = 0, 0, (s_resultado - s_fator) / s_fator2)
        WHEN id_formula_resultado = 13 THEN iif(s_fator = 0, 0, (s_resultado / s_fator) - (s_fator2 / s_fator))
        when id_formula_resultado = 14 THEN s_fator - s_resultado
        when id_formula_resultado = 15 THEN iif((s_fator = 0 or s_fator3 = 0 or s_fator2 = 0), 0, (s_resultado / s_fator)/(s_fator2 / s_fator3))
    END AS resultado,

    CASE
        WHEN id_formula_meta = 1  THEN iif(s_hc = 0,0, s_meta / s_hc)
        WHEN id_formula_meta = 2  THEN iif(s_fator2 = 0,0,s_fator / s_fator2)
        WHEN id_formula_meta = 3  THEN s_fator4
        WHEN id_formula_meta = 4  THEN IIF(s_fator3 = 0,0,s_fator4 / s_fator3)
        WHEN id_formula_meta = 5  THEN IIF(s_hc = 0,0,s_meta / s_hc)
        WHEN id_formula_meta = 6  THEN s_fator2
        WHEN id_formula_meta = 7  THEN IIF(s_fator = 0,0,s_meta / s_fator)
        WHEN id_formula_meta = 8  THEN IIF(s_fator2 = 0,0,s_meta / s_fator2)
        WHEN id_formula_meta = 9  THEN IIF(s_fator4 = 0,0,s_meta / s_fator4)
        WHEN id_formula_meta = 10 THEN IIF(s_fator = 0,0,s_fator2 / s_fator)
        WHEN id_formula_meta = 11 THEN IIF(s_fator3 = 0,0,s_fator2 / s_fator3)
    END AS meta

INTO #base
FROM #agg a
left join #formulas f on a.id_indicador = f.id_indicador

SELECT DISTINCT
    segmento as atributo,
    b.id_indicador,
    resultado,
    case when
        fi.id_formato = 3 then meta * 100
    else meta end as meta,
    CASE 
        WHEN id_formula_atingimento = 2 THEN IIF(resultado = 0, 10, meta/resultado)
        WHEN id_formula_atingimento = 3 THEN IIF(meta = 0 OR resultado <= 0, 0, resultado/meta)
        WHEN id_formula_atingimento = 4 THEN IIF(resultado > meta, meta/resultado, resultado/meta)
        WHEN id_formula_atingimento = 6 THEN IIF(meta = -1, 0, (resultado+1)/(meta+1))
        WHEN id_formula_atingimento = 7 THEN IIF(meta > 0.00001, resultado/meta,IIF(resultado = 0, 1, resultado/meta))
        WHEN id_formula_atingimento = 8 THEN iif(meta = 0, 0, IIF(resultado/meta >= 1, 0, resultado/meta))
        WHEN id_formula_atingimento = 9 THEN IIF(resultado >= 0, 10, meta/resultado)
        when id_formula_atingimento = 10 THEN IIF(meta = 0, 0, IIF(resultado > meta, meta/resultado, resultado/meta))
        WHEN id_formula_atingimento = 11 THEN IIF((resultado = 0 OR meta = 0), 0, meta/resultado)
        ELSE NULL
    END AS atingimento
into #atingimento
FROM #base b
left join #fi fi
    on fi.id_indicador = b.id_indicador

--------

---- limites inferior e superior ----

select *
into #limites_indicadores
from (values
    (901,94,96.5)
) v(id_indicador, faixa_inferior, faixa_superior)

--------

---- query final ----
insert into robbysonmatriz.dbo.meta_variacao_sistema_matriz
select distinct
    cast(getdate() as date) as data_insercao,
    sm.periodo,
    sm.atributo,
    sm.id_indicador,
    ti.indicador_nome as nome_indicador,
    fi.formato as formato_indicador,
    ti.tipo as tipo_indicador,
    cast(atng.meta as decimal(10,2)) as meta,
    round(atng.atingimento, 2) as atingimento,
    f.fator,
    sm.pode_facilitar,
    case 
        when lim.id_indicador is not null then
            case 
                when (atng.meta * f.fator) > lim.faixa_superior 
                    then cast(lim.faixa_superior as decimal(10,2))
                when (atng.meta * f.fator) < lim.faixa_inferior 
                    then cast(lim.faixa_inferior as decimal(10,2))
                else 
                    cast(round(
                        cast(atng.meta as decimal(18,2)) * f.fator
                    ,2) as decimal(10,2))
            end
        else 
            case 
                when fi.formato = 'integer' 
                    then cast(round(atng.meta * f.fator, 0) as decimal(10,2))
                else 
                    cast(round(
                        cast(atng.meta as decimal(18,2)) * f.fator
                    ,2) as decimal(10,2))
            end
    end as meta_variacao
from #sm sm
left join #ti ti
    on ti.id_indicador = sm.id_indicador
left join #fi fi
    on fi.id_indicador = sm.id_indicador
left join #atingimento atng
    on atng.atributo = sm.atributo
   and atng.id_indicador = sm.id_indicador
left join #limites_indicadores lim
    on lim.id_indicador = sm.id_indicador
cross apply (
    select 
        cast(
            case 
                when isnull(atng.atingimento, 0) >= 1 then 
                    case 
                        when ti.tipo = 'maior melhor' then 1.015
                        else 0.985
                    end
                else 
                    case 
                        when sm.pode_facilitar = 1 then 
                            case 
                                when ti.tipo = 'maior melhor' then 0.985
                                else 1.015
                            end
                        else 1.000
                    end
            end 
        as decimal(6,3)) as fator
) f
where atingimento is not null
and sm.atributo in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))
and not exists (
    select 1
    from #ids_quebra_semanal q
    where q.id_indicador = sm.id_indicador
    and q.atributo = sm.atributo
)


drop table #ids_quebra_semanal
drop table #ti
drop table #ids_desconsiderar
drop table #fi
drop table #limites_indicadores
drop table #sm
drop table #formulas
drop table #agg
drop table #base
drop table #atingimento
"""

REPLICADOR_IMPORT_MATRIZ = """
use robbysonmatriz;

SET NOCOUNT ON;

-- O indice 0 significa proximo mes, -1 mes atual, -2 mês anterior, -3 dois meses atras e assim por diante
declare @indice integer = -2;

if object_id('tempdb..#rby_indicador') is not null drop table #rby_indicador;
if object_id('tempdb..#hmn') is not null drop table #hmn;

-- geração da temp do rby_indicador
select
    id_indicador,
    indicador_nome,
    case
        when indicador_nome like '%semanal%' then 'SIM'
        when indicador_nome like '%mensal%' then 'NÃO'
        else 'NÃO'
    end as acumulado,
    case
        when indicador_nome like '%semanal%' then 'SEMANAL'
        when indicador_nome like '%mensal%' then 'MENSAL'
        else 'DIARIO'
    end as esquema_acumulado,
    case
        when tipo_medida_indicador = 'admin_generic_integer' then 'INTEIRO'
        when tipo_medida_indicador = 'admin_generic_float' then 'DECIMAL'
        when tipo_medida_indicador = 'admin_generic_percentage' then 'PERCENTUAL'
        when tipo_medida_indicador = 'admin_generic_hour' then 'HORA'
        else 'INTEIRO'
    end as formato
into #rby_indicador
from robbysonmatriz.dbo.indicador (nolock)
where indicador_nome <> 'descontinuado'
  and indicador_nome <> 'indicador disponivel';

-- geração da temp do homminum
select distinct
    atributo
into #hmn
from robbysonmatriz.dbo.hmn (nolock)
where --data = dateadd(d, 1, eomonth(getdate(), @indice)) -- modificado em 04/02/2026 para a data d-1 em vez da data do mes em questão para evitar problemas com atributos que não aparecem na pagina apoio
data = convert(date, getdate()-1)
and situacaohominum in ('ativo', 'treinamento')
and tipohierarquia = 'operação'
and nivelhierarquico = 'operacional'
and funcaorm not like 'auxiliar%'
and funcaorm not like 'analista%'
and atributo is not null
and atributo not like '%salario_funcao%'


-- inserção das matrizes na sistema_matriz
insert into robbysonmatriz.dbo.sistema_matriz
select distinct
    UPPER(im.atributo) as atributo,
    concat(im.id_indicador, ' - ', im.nome_indicador) as id_nome_indicador,
    case when
        ri.formato = 'hora' then 
            case when
                im.meta > 2 then
                    convert(varchar(8), CAST(DATEADD(SECOND, im.meta, '00:00:00') AS TIME))
                ELSE
                    convert(varchar(8), CAST(DATEADD(SECOND, round(im.meta*86400, 0), '00:00:00') AS TIME))
            end
    else 
        convert(varchar, coalesce(mv.meta_variacao, im.meta))
    end as meta,
    --case when ri.formato = 'hora' then convert(varchar(8), convert(time, convert(datetime, im.meta))) else convert(varchar, meta) end as meta_formatada_import, -- meta antes do meta smart
    ganho_g1 as moedas,
    UPPER(ri.formato) as tipo_indicador,
    case when LOWER(ri.acumulado) = 'não' then 'NAO' else UPPER(ri.acumulado) end as acumulado,
    UPPER(ri.esquema_acumulado) as esquema_acumulado,

    dateadd(month, 2, im.data_inicio) as data_inicio, -- para inserção no mes seguinte ao atual
    case when 
        (day(im.data_fim) = 28 or day(im.data_fim) = 30 or day(im.data_fim) = 31) 
            then eomonth(dateadd(month, 2, im.data_fim))
        else dateadd(month, 2, im.data_fim)
    end as data_fim, -- para inserção no mes seguinte ao atual
    dateadd(d, 1, eomonth(im.data_inicio, 1)) as periodo, -- para inserção no mes seguinte ao atual

    UPPER(escala) as escala,
    case when mv.meta_variacao is null then 'Meta Original' else 'Meta Smart' end as descricao,
    0 as ativo,
    NULL as dmm,
    0 as qualidade,
    0 as da_qualidade,
    '' as data_da_qualidade,
    0 as planejamento,
    0 as da_planejamento,
    '' as data_da_planejamento,
    0 as exop,
    0 as da_exop,
    '' as data_da_exop,
    0 as operacao,
    0 as da_operacao,
    '' as data_da_operacao,
    0 as importado,
    '' as data_importacao,
    '' as meta_apoio,
    case 
    when ri.formato = 'hora' then 
        convert(
            varchar(8), 
            convert(time, convert(datetime, coalesce(mv.meta_variacao, im.meta)))
        )
    else 
        convert(varchar, coalesce(mv.meta_variacao, im.meta))
    end as meta_final,
    '' as id_incluso,
    '' as id_excluso,
    1 as importacao_valida,
    0 as matriz_coletada,
    '' as justificativa_meta,
    '' as observacao_operacao,
    im.Id_Indicador as id_indicador,
    0 as moedas_apoio
FROM robbyson.rby.import_matriz im (NOLOCK)
left join #rby_indicador ri
       on im.id_indicador = ri.id_indicador
inner join #hmn hmn
       on im.atributo = hmn.atributo
left join robbysonmatriz.dbo.meta_variacao_sistema_matriz (nolock) mv
       on im.atributo = mv.atributo
       and im.Id_Indicador = mv.id_indicador
       and mv.periodo = dateadd(d, 1, eomonth(getdate(), -2))
where im.data_inicio >= dateadd(d, 1, eomonth(getdate(), @indice))
and im.data_fim <= eomonth(getdate(), @indice+1)
and im.ativo > 0
and im.atributo not in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))

-- inserção dos indicadores de querencia para os atributos que não tiverem matriz no mes escolhido
; with atributos_sem_dados as (
    select distinct h.atributo
    from #hmn h
    left join robbyson.rby.import_matriz (nolock) im
        on im.atributo = h.atributo
       and im.data_inicio >= dateadd(d, 1, eomonth(getdate(), @indice))
       and im.data_fim <= eomonth(getdate(), @indice+1)
       and im.ativo > 0
    where im.atributo is null
)

, indicadores_padrao as (
    select *
    from (values
        ('901 - % DISPONIBILIDADE','94',35,'PERCENTUAL'),
        ('15 - TEMPO LOGADO','00:00:00',0,'HORA'),
        ('25 - NR17','00:00:00',0,'HORA'),
        ('6 - % ABSENTEÍSMO','5',0,'PERCENTUAL')
    ) v(id_nome_indicador, meta, moedas, tipo_indicador)
)

insert into robbysonmatriz.dbo.sistema_matriz
select
    upper(a.atributo) as atributo,
    i.id_nome_indicador,
    i.meta,
    i.moedas,
    i.tipo_indicador,
    'NAO' as acumulado,
    'DIARIO' as esquema_acumulado,
    
    dateadd(d, 1, eomonth(getdate(), @indice+2)) as data_inicio, -- para inserção no mes seguinte ao atual
    eomonth(getdate(), @indice+3) as data_fim, -- para inserção no mes seguinte ao atual
    dateadd(d, 1, eomonth(getdate(), @indice+2)) as periodo, -- para inserção no mes seguinte ao atual

    '6X1' as escala,
    'Matriz Querencia' as descricao,
    0 as ativo,
    null as dmm,
    0 as qualidade,
    0 as da_qualidade,
    '' as data_da_qualidade,
    0 as planejamento,
    0 as da_planejamento,
    '' as data_da_planejamento,
    0 as exop,
    0 as da_exop,
    '' as data_da_exop,
    0 as operacao,
    0 as da_operacao,
    '' as data_da_operacao,
    0 as importado,
    '' as data_importacao,
    '' as meta_apoio,
    i.meta as meta_final,
    '' as id_incluso,
    '' as id_excluso,
    1 as importacao_valida,
    0 as matriz_coletada,
    '' as justificativa_meta,
    '' as observacao_operacao,
    LTRIM(RTRIM(LEFT(i.id_nome_indicador, CHARINDEX('-', i.id_nome_indicador) - 1))) as id_indicador,
    0 as moedas_apoio
from atributos_sem_dados a
cross join indicadores_padrao i
where a.atributo not in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))

drop table #rby_indicador;
drop table #hmn;
"""

REPLICADOR_SISTEMA_MATRIZ = """
use robbysonmatriz;

SET NOCOUNT ON;

if object_id('tempdb..#metas') is not null drop table #metas;
if object_id('tempdb..#hmn') is not null drop table #hmn;

-- geração da temp do homminum
select distinct
    atributo
into #hmn
from robbysonmatriz.dbo.hmn (nolock)
where --data = dateadd(d, 1, eomonth(getdate(), @indice)) -- modificado em 04/02/2026 para a data d-1 em vez da data do mes em questão para evitar problemas com atributos que não aparecem na pagina apoio
data = convert(date, getdate()-1)
and situacaohominum in ('ativo', 'treinamento')
and tipohierarquia = 'operação'
and nivelhierarquico = 'operacional'
and funcaorm not like 'auxiliar%'
and funcaorm not like 'analista%'
and atributo is not null
and atributo not like '%salario_funcao%'


-- coleta da meta variação ou meta original
select
    sm.data_inicio,
    sm.atributo,
    sm.id_indicador,
    case when mv.meta_variacao is null then 'Meta Original' else 'Meta Smart' end as descricao,
    case
        when i.id_formato = 4 and mv.meta_variacao is not null
            then convert(varchar(8), cast(dateadd(second, round(mv.meta_variacao, 0), '00:00:00') as time))
        when i.id_formato = 4
            then convert(varchar(8), sm.meta_final)
        when mv.meta_variacao is not null
            then convert(varchar, mv.meta_variacao)
        else
            convert(varchar, sm.meta_final)
    end as meta
into #metas
from robbysonmatriz.dbo.sistema_matriz (nolock) sm
left join robbysonmatriz.dbo.meta_variacao_sistema_matriz (nolock) mv
    on sm.id_indicador = mv.id_indicador
    and sm.atributo = mv.atributo
    and mv.periodo = DATEADD(d, 1, EOMONTH(GETDATE(), -1))
left join robbyson.dbo.rby_indicador (nolock) i 
    on i.id_indicador = sm.Id_Indicador
where sm.periodo = dateadd(d, 1, eomonth(getdate(), -1))


insert into robbysonmatriz.dbo.sistema_matriz
select
    sm.atributo,
    sm.id_nome_indicador,
    m.meta as meta,
    sm.moedas,
    sm.tipo_indicador,
    sm.acumulado,
    sm.esquema_acumulado,
    dateadd(d, 1, eomonth(getdate(), 0)) as data_inicio,
    case when 
        (day(sm.data_fim) = 28 or day(sm.data_fim) = 30 or day(sm.data_fim) = 31) 
            then eomonth(dateadd(month, 1, sm.data_fim))
        else dateadd(month, 1, sm.data_fim)
    end as data_fim, -- para inserção no mes seguinte ao atual,
    dateadd(d, 1, eomonth(getdate(), 0)) as periodo,
    escala,
    m.descricao,
    0 as ativo,
    NULL as dmm,
    0 as qualidade,
    0 as da_qualidade,
    '' as data_da_qualidade,
    0 as planejamento,
    0 as da_planejamento,
    '' as data_da_planejamento,
    0 as exop,
    0 as da_exop,
    '' as data_da_exop,
    0 as operacao,
    0 as da_operacao,
    '' as data_da_operacao,
    0 as importado,
    '' as data_importacao,
    '' as meta_apoio,
    m.meta as meta_final,
    0 as id_incluso,
    0 as id_excluso,
    1 as importacao_valida,
    0 as matriz_coletada,
    '' as justificativa_meta,
    '' as observacao_operacao,
    sm.id_indicador,
    0 as moedas_apoio
from robbysonmatriz.dbo.sistema_matriz (nolock) sm
left join #metas m
    on sm.id_indicador = m.id_indicador
    and sm.atributo = m.atributo
    and sm.data_inicio = m.data_inicio
where sm.periodo = dateadd(d, 1, eomonth(getdate(), -1))
and sm.atributo in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))
order by sm.atributo


-- matriz querencia para atributos válidos no hominum que não estão na sistema matriz no mes atual
; with atributos_sem_dados as (
    select distinct h.atributo
    from #hmn h
    left join robbysonmatriz.dbo.sistema_matriz (nolock) sm
        on sm.atributo = h.atributo
       and sm.periodo = dateadd(d, 1, eomonth(getdate(), -1))
    where sm.atributo is null
)

, indicadores_padrao as (
    select *
    from (values
        ('901 - % DISPONIBILIDADE','94',35,'PERCENTUAL'),
        ('15 - TEMPO LOGADO','00:00:00',0,'HORA'),
        ('25 - NR17','00:00:00',0,'HORA'),
        ('6 - % ABSENTEÍSMO','5',0,'PERCENTUAL')
    ) v(id_nome_indicador, meta, moedas, tipo_indicador)
)


insert into robbysonmatriz.dbo.sistema_matriz
select
    upper(a.atributo) as atributo,
    i.id_nome_indicador,
    i.meta,
    i.moedas,
    i.tipo_indicador,
    'NAO' as acumulado,
    'DIARIO' as esquema_acumulado,
    dateadd(d, 1, eomonth(getdate(), 0)) as data_inicio,
    eomonth(getdate(), 1) as data_fim,
    dateadd(d, 1, eomonth(getdate(), 0)) as periodo,
    '6X1' as escala,
    'Matriz Querencia' as descricao,
    0 as ativo,
    null as dmm,
    0 as qualidade,
    0 as da_qualidade,
    '' as data_da_qualidade,
    0 as planejamento,
    0 as da_planejamento,
    '' as data_da_planejamento,
    0 as exop,
    0 as da_exop,
    '' as data_da_exop,
    0 as operacao,
    0 as da_operacao,
    '' as data_da_operacao,
    0 as importado,
    '' as data_importacao,
    '' as meta_apoio,
    i.meta as meta_final,
    '' as id_incluso,
    '' as id_excluso,
    1 as importacao_valida,
    0 as matriz_coletada,
    '' as justificativa_meta,
    '' as observacao_operacao,
    LTRIM(RTRIM(LEFT(i.id_nome_indicador, CHARINDEX('-', i.id_nome_indicador) - 1))) as id_indicador,
    0 as moedas_apoio
from atributos_sem_dados a
cross join indicadores_padrao i
where a.atributo in (select distinct atributo from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock))


drop table #metas
drop table #hmn
"""

try:
    conn = None
    cursor = None
    try:
        conn = pyodbc.connect(CONNECTION_STRING, autocommit = False)
        cursor = conn.cursor()
    except Exception as e:
        write_log(f"Erro ao criar conexão: {repr(e)}")
        raise

    write_log("Iniciando processo de replicação das matrizes...")

    try:
        cursor.execute(META_VARIACAO_IMPORT_MATRIZ)
    except Exception as e:
        write_log(f"Erro na META_VARIACAO_IMPORT_MATRIZ: {repr(e)}")
        conn.rollback()
        raise
    try:
        cursor.execute(META_VARIACAO_SISTEMA_MATRIZ)
    except Exception as e:
        write_log(f"Erro na META_VARIACAO_SISTEMA_MATRIZ: {repr(e)}")
        conn.rollback()
        raise
    try:
        cursor.execute(REPLICADOR_IMPORT_MATRIZ)
    except Exception as e:
        write_log(f"Erro na REPLICADOR_IMPORT_MATRIZ: {repr(e)}")
        conn.rollback()
        raise
    try:
        cursor.execute(REPLICADOR_SISTEMA_MATRIZ)
    except Exception as e:
        write_log(f"Erro na REPLICADOR_SISTEMA_MATRIZ: {repr(e)}")
        conn.rollback()
        raise

    try:
        conn.commit()
    except Exception as e:
        write_log(f"Erro ao commitar a conexão: {repr(e)}")
        conn.rollback()
        raise

    write_log("Replicação das matrizes finalizada com sucesso...")

finally:
    if cursor is not None:
        try:
            cursor.close()
        except Exception as e:
            write_log(f"Erro ao fechar cursor: {repr(e)}")

    if conn is not None:
        try:
            conn.close()
        except Exception as e:
            write_log(f"Erro ao fechar conexão: {repr(e)}")