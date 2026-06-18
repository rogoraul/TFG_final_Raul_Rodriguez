import numpy as np
from numba import jit

@jit(nopython=True)
def calc_divergencias_numba(prices, indicators, pivot_types, tolerance, ind_tolerance):
    """
    Calcula divergencias usando Numba para alta velocidad.
    
    Args:
        prices (np.array): Array de precios (close).
        indicators (np.array): Array del indicador (RSI, EWO, etc).
        pivot_types (np.array): Array de tipos de pivote (1, -1, 0).
        tolerance (float): Tolerancia porcentual para el precio.
        ind_tolerance (float): Tolerancia absoluta para el indicador.
        
    Returns:
        tuple: Arrays numpy para cada tipo de divergencia (reg_a, reg_b, ocult_a, ocult_b).
    """
    n = len(prices)
    
    # Inicializamos arrays de salida con ceros (int8 para ahorrar memoria, o float si prefieres)
    # Usamos float para mantener consistencia con NaN si fuera necesario, pero el original usa 0 y -1/1.
    res_reg_a = np.zeros(n, dtype=np.int8)
    res_reg_b = np.zeros(n, dtype=np.int8)
    res_ocult_a = np.zeros(n, dtype=np.int8)
    res_ocult_b = np.zeros(n, dtype=np.int8)
    
    # Encontramos los índices de los pivotes
    # En numba np.where retorna una tupla, tomamos el primer elemento
    pivot_indices = np.where(pivot_types != 0)[0]
    num_pivots = len(pivot_indices)
    
    if num_pivots < 3:
        return res_reg_a, res_reg_b, res_ocult_a, res_ocult_b
    
    # Iteramos sobre los pivotes
    for i in range(2, num_pivots):
        curr_idx = pivot_indices[i]
        prev_idx = pivot_indices[i-2]
        
        tipo = pivot_types[curr_idx]
        prev_tipo = pivot_types[prev_idx]
        
        # Deben ser del mismo tipo (Pico-Pico o Valle-Valle)
        # Como saltamos de 2 en 2 en indices_pivotes, normalmente alternan High/Low/High/Low...
        # Así que i e i-2 deberían ser iguales. Por seguridad chequeamos.
        if tipo != prev_tipo:
            continue
            
        precio_curr = prices[curr_idx]
        precio_prev = prices[prev_idx]
        ind_curr = indicators[curr_idx]
        ind_prev = indicators[prev_idx]
        
        # Diferencia porcentual del precio
        if precio_prev == 0: # Evitar div por cero
            continue
            
        diff_precio = (precio_curr - precio_prev) / precio_prev
        es_mismo_nivel = abs(diff_precio) <= tolerance
        
        # Chequeos de indicador
        # Nota: En Python puro abs(val) funciona, en numba también.
        
        indicador_baja = ind_curr < (ind_prev - ind_tolerance)
        indicador_sube = ind_curr > (ind_prev + ind_tolerance)
        
        # ------------------------------------------------------------------
        # PICOS (HIGHS / 1) -> Buscamos SEÑALES BAJISTAS (VENTA)
        # ------------------------------------------------------------------
        if tipo == 1:
            # REGULAR (Precio Sube/Igual, Indicador Baja) -> REVERSIÓN
            if indicador_baja:
                if es_mismo_nivel:
                    res_reg_b[curr_idx] = -1 # Doble Techo
                elif diff_precio > tolerance:
                    res_reg_a[curr_idx] = -1 # Nuevo Máximo

            # OCULTA (Precio Baja/Igual, Indicador Sube) -> CONTINUACIÓN
            elif indicador_sube:
                if es_mismo_nivel:
                    res_ocult_b[curr_idx] = -1 # Doble Techo (Raro)
                elif diff_precio < -tolerance:
                    res_ocult_a[curr_idx] = -1 # Máximo Menor

        # ------------------------------------------------------------------
        # VALLES (LOWS / -1) -> Buscamos SEÑALES ALCISTAS (COMPRA)
        # ------------------------------------------------------------------
        elif tipo == -1:
            # REGULAR (Precio Baja/Igual, Indicador Sube) -> REVERSIÓN
            if indicador_sube:
                if es_mismo_nivel:
                    res_reg_b[curr_idx] = 1 # Doble Suelo
                elif diff_precio < -tolerance:
                    res_reg_a[curr_idx] = 1 # Nuevo Mínimo

            # OCULTA (Precio Sube/Igual, Indicador Baja) -> CONTINUACIÓN
            elif indicador_baja:
                if es_mismo_nivel:
                    res_ocult_b[curr_idx] = 1 # Doble Suelo (Raro)
                elif diff_precio > tolerance:
                    res_ocult_a[curr_idx] = 1 # Mínimo Creciente
                    
    return res_reg_a, res_reg_b, res_ocult_a, res_ocult_b
