from datetime import datetime

UPDATE_ROLE = """
    update robbysonmatriz.dbo.acessos_sistema_matriz 
    set role = original_role
"""

UPDATE_MOSTRAR_ATRIBUTO = """
    update robbysonmatriz.dbo.perfis_temporarios_sistema_matriz 
    set mostrar_atributo = 0 
    where mostrar_atributo = 1
"""

UPDATE_PROJETO_CEGONHA = """
    update robbysonmatriz.dbo.sistema_matriz 
    set meta_final = 87.7 
    where periodo = dateadd(d, 1, eomonth(getdate(), -1)) 
    and atributo like '%projeto_cegonha%' 
    and id_indicador = 901
"""

MOVER_HISTORICO = """
    declare @periodo date = cast((select min(periodo) from robbysonmatriz.dbo.sistema_matriz (nolock)) as date);

    insert into robbysonmatriz.dbo.sistema_matriz_historico
    select 
        * 
    from 
        robbysonmatriz.dbo.sistema_matriz (nolock)
    where
        periodo = @periodo

    delete from robbysonmatriz.dbo.sistema_matriz where periodo = @periodo
"""

SISTEMA_MATRIZ = "EXEC dbo.sp_ins_sistema_matriz"

RM_PT1 = "EXEC dbo.sp_ins_Robbyson_Matriz_pt1"

RM_PT2 = "EXEC dbo.sp_ins_Robbyson_Matriz_pt2"

ATT_PUBLICO_INSERT_MANUAL = f"""
    insert into robbysonmatriz.dbo.publico_piloto_sistema_matriz (atributo)
    select distinct
        atributo, '', '', '', cast(getdate() as date)
    from robbysonmatriz.dbo.sistema_matriz (nolock) sm
    where 
        periodo = dateadd(d, 1, eomonth(getdate(), -1))
        and descricao like '%em {datetime.now().date()}'
        and importado = 0
        and importacao_valida = 1
        and matriz_coletada = 0
        and ativo = 1
        and not exists (
            select 1 
            from robbysonmatriz.dbo.publico_piloto_sistema_matriz (nolock) pp
            where pp.atributo = sm.atributo
        )
"""

CHECK_RESULTADO = "EXEC dbo.sp_ins_check_resultado_sistema_matriz"

DADOS_HISTORICOS = """
    truncate table robbyson.dbo.dados_historicos_sistema_matriz


    select 
        id_indicador,
        case 
            when formula_perc_atingimento like '%meta/resultado%' then 'menor melhor'
            when formula_perc_atingimento like '%resultado/meta%' then 'maior melhor'
        else null end as tipo_indicador
    into #ti
    from robbyson.rby.indicador (nolock)
    where formula_perc_atingimento is not null


    select 
        id_indicador, 
        id_formula_resultado,
        id_formula_meta,
        id_formula_atingimento,
        id_formato,
        case when 
            formato = 'coin' then 'integer' 
            else formato 
        end as formato 
    into 
        #fi
    from 
        robbyson.dbo.rby_indicador (nolock) 
    where 
        formato is not null


    SELECT
        segmento,
        id_indicador,
        SUM(resultado)  AS s_resultado,
        SUM(fator)      AS s_fator,
        SUM(fator_2)    AS s_fator2,
        SUM(fator_3)    AS s_fator3,
        SUM(fator_4)    AS s_fator4,
        SUM(meta)       AS s_meta,
        count(chave_externa)         AS s_hc
    INTO 
        #agg
    FROM 
        robbyson.rby.performance (NOLOCK)
    WHERE 
        data >= dateadd(d, 1, eomonth(getdate(), -4)) 
        and data < dateadd(d, 1, eomonth(getdate(), -1))
    GROUP BY
        id_indicador,
        segmento
    create index ix_agg on #agg (segmento, id_indicador);

    SELECT
        a.segmento,
        a.id_indicador,
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
    INTO 
        #base
    FROM 
        #agg a
    left join #fi fi 
        on a.id_indicador = fi.id_indicador
    create index ix_base on #base (segmento, id_indicador);


    insert into robbyson.dbo.dados_historicos_sistema_matriz
    SELECT DISTINCT
        b.segmento as atributo,
        b.id_indicador,
        ti.tipo_indicador,
        cast(resultado as decimal(18, 4)) as resultado,
        cast(case when
            fi.id_formato = 3 then meta * 100
        else meta end as decimal(18, 4)) as meta,
        cast(CASE 
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
        END as decimal(18, 4)) as atingimento,
        dateadd(d, 1, eomonth(getdate(), -4)) as data_inicio_avaliacao,
        eomonth(getdate(), -1) as data_fim_avaliacao,
        getdate() as data_execucao
    FROM 
        #base b
    left join #fi fi 
        on b.id_indicador = fi.id_indicador
    left join #ti ti 
        on b.id_indicador = ti.id_indicador


    drop table #ti
    drop table #fi
    drop table #agg
    drop table #base
"""