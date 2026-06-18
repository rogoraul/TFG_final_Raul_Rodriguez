import pandas as pd
import numpy as np
import pandas_ta_classic as ta
from zigzag import peak_valley_pivots, peak_valley_pivots_dynamic, pivots_to_modes
from backtests.enbolsa.divergencia_numba import calc_divergencias_numba

class AnalizadorDeContexto:
    def __init__(self, trend_fast=50, trend_slow=150, trend_type='wma', 
                 zigzag_deviation=0.05, tolerance=0.003,
                 zigzag_mode='fixed', zigzag_atr_multiplier=5.0,
                 zigzag_min_periods=200, zigzag_shift_bars=1,
                 zigzag_floor=None, zigzag_ceiling=None):
        """
        Configura el análisis de tendencia.
        
        Args:
            trend_fast (int): Periodo de la media rápida estructural (Ej. 50).
            trend_slow (int): Periodo de la media lenta estructural (Ej. 150).
            trend_type (str): Tipo de media ('wma', 'sma', 'ema').
        """
        self.trend_fast = trend_fast
        self.trend_slow = trend_slow
        self.trend_type = trend_type.lower()
        self.zigzag_deviation = zigzag_deviation
        self.tolerance = tolerance
        self.zigzag_mode = zigzag_mode
        self.zigzag_atr_multiplier = zigzag_atr_multiplier
        self.zigzag_min_periods = zigzag_min_periods
        self.zigzag_shift_bars = zigzag_shift_bars
        self.zigzag_floor = zigzag_floor
        self.zigzag_ceiling = zigzag_ceiling

    def _build_zigzag_deviation_series(self, df):
        fallback = float(self.zigzag_deviation)
        base_series = pd.Series(
            np.full(len(df), fallback, dtype=float),
            index=df.index,
            name='ZIGZAG_DEVIATION',
        )

        if self.zigzag_mode != 'expanding_atr_median':
            return base_series
        if 'ATR' not in df.columns or 'close' not in df.columns:
            return base_series

        atr = pd.to_numeric(df['ATR'], errors='coerce')
        close = pd.to_numeric(df['close'], errors='coerce').replace(0.0, np.nan)
        atr_pct = (atr / close).replace([np.inf, -np.inf], np.nan)

        min_periods = max(int(self.zigzag_min_periods), 1)
        shift_bars = max(int(self.zigzag_shift_bars), 0)

        dynamic = atr_pct.expanding(min_periods=min_periods).median()
        if shift_bars > 0:
            dynamic = dynamic.shift(shift_bars)
        dynamic = dynamic * float(self.zigzag_atr_multiplier)
        dynamic = dynamic.fillna(fallback)

        if self.zigzag_floor is not None:
            dynamic = dynamic.clip(lower=float(self.zigzag_floor))
        if self.zigzag_ceiling is not None:
            dynamic = dynamic.clip(upper=float(self.zigzag_ceiling))

        dynamic = dynamic.replace([np.inf, -np.inf], np.nan).fillna(fallback)
        dynamic = dynamic.clip(lower=1e-6)
        dynamic.name = 'ZIGZAG_DEVIATION'
        return dynamic

    def calcular_tendencia(self, df_original):
        """
        Determina la tendencia estructural del mercado.
        No modifica las columnas existentes de medias, crea sus propias columnas de tendencia.
        
        Returns:
            df con columna 'TENDENCIA_ESTRUCTURAL': 1 (Alcista), -1 (Bajista)
        """
        df = df_original.copy()
        
        col_fast = f'TREND_{self.trend_type.upper()}_{self.trend_fast}'
        col_slow = f'TREND_{self.trend_type.upper()}_{self.trend_slow}'
        
        if self.trend_type == 'wma':
            df[col_fast] = ta.wma(df['close'], length=self.trend_fast)
            df[col_slow] = ta.wma(df['close'], length=self.trend_slow)
        elif self.trend_type == 'sma':
            df[col_fast] = ta.sma(df['close'], length=self.trend_fast)
            df[col_slow] = ta.sma(df['close'], length=self.trend_slow)
        elif self.trend_type == 'ema':
            df[col_fast] = ta.ema(df['close'], length=self.trend_fast)
            df[col_slow] = ta.ema(df['close'], length=self.trend_slow)
        
        diff = df[col_fast] - df[col_slow]
        df['TENDENCIA_ESTRUCTURAL'] = np.sign(diff)
        
        return df

    def calcular_zigzag(self, df):
        """
        Aplica tu función local peak_valley_pivots.
        """
        df = df.copy()
        values = df['close'].values

        deviation_series = self._build_zigzag_deviation_series(df)
        deviation_values = pd.to_numeric(
            deviation_series, errors='coerce'
        ).fillna(float(self.zigzag_deviation)).to_numpy(dtype=np.float64, copy=False)

        if np.allclose(deviation_values, deviation_values[0]):
            pivots = peak_valley_pivots(
                values,
                float(deviation_values[0]),
                -float(deviation_values[0]),
            )
        else:
            pivots = peak_valley_pivots_dynamic(
                values,
                deviation_values,
                -deviation_values,
            )
        modes = pivots_to_modes(pivots)

        df['ZIGZAG_DEVIATION'] = deviation_values
        df['PIVOT_TYPE'] = pivots # 1=High, -1=Low
        df['PIVOT_VALUE'] = np.where(df['PIVOT_TYPE'] != 0, df['close'], np.nan)
        df['ZIGZAG_DIRECTION'] = modes
        
        return df
    
    def _confirmar_pivotes(self, df):
        """
        Desplaza cada pivot ZigZag al bar donde se confirma en tiempo real.
        Elimina el Look-Ahead Bias en la FUENTE.
        
        - High (pico): confirmado cuando low cae >= desviación desde el pico.
        - Low (valle): confirmado cuando high sube >= desviación desde el valle.
        
        El VALUE del pivot se preserva (precio real del extremo).
        Solo el TIME se desplaza al momento de confirmación.
        """
        deviation_values = (
            pd.to_numeric(df['ZIGZAG_DEVIATION'], errors='coerce').to_numpy(dtype=float, copy=False)
            if 'ZIGZAG_DEVIATION' in df.columns
            else np.full(len(df), float(self.zigzag_deviation), dtype=float)
        )
        
        original_types = df['PIVOT_TYPE'].values.copy()
        original_values = df['PIVOT_VALUE'].values.copy()
        highs = df['high'].values
        lows = df['low'].values
        
        # Arrays para los pivotes confirmados
        new_types = np.zeros(len(df), dtype=int)
        new_values = np.full(len(df), np.nan)
        delay_bars = np.full(len(df), np.nan)  # diagnóstico: cuántas velas de delay
        pivot_dev = np.full(len(df), np.nan)
        
        pivot_positions = np.where(original_types != 0)[0]
        
        for pos in pivot_positions:
            ptype = int(original_types[pos])
            pval = original_values[pos]
            
            if np.isnan(pval):
                continue

            desviacion = deviation_values[pos]
            if np.isnan(desviacion) or desviacion <= 0:
                desviacion = float(self.zigzag_deviation)

            dev_price = pval * desviacion  # desviación en unidades de precio
            
            # Buscar primera vela posterior que confirma el giro
            confirmed_at = -1
            for j in range(pos + 1, len(df)):
                if ptype == 1:  # High: confirmado cuando low cae
                    if lows[j] <= pval - dev_price:
                        confirmed_at = j
                        break
                else:  # Low: confirmado cuando high sube
                    if highs[j] >= pval + dev_price:
                        confirmed_at = j
                        break
            
            if confirmed_at >= 0:
                # Si ya hay un pivot en ese bar, el más reciente gana
                new_types[confirmed_at] = ptype
                new_values[confirmed_at] = pval  # VALUE real, no el del bar actual
                delay_bars[confirmed_at] = confirmed_at - pos
                pivot_dev[confirmed_at] = desviacion
        
        df['PIVOT_TYPE'] = new_types
        df['PIVOT_VALUE'] = np.where(new_types != 0, new_values, np.nan)
        df['PIVOT_DELAY'] = np.where(new_types != 0, delay_bars, np.nan)
        df['PIVOT_DEV'] = np.where(new_types != 0, pivot_dev, np.nan)
        
        # Recalcular ZIGZAG_DIRECTION desde los pivotes confirmados
        df['ZIGZAG_DIRECTION'] = np.nan
        confirmed_pivots = df.index[df['PIVOT_TYPE'] != 0]
        for k in range(len(confirmed_pivots) - 1):
            idx_start = confirmed_pivots[k]
            idx_end = confirmed_pivots[k + 1]
            ptype_start = df.at[idx_start, 'PIVOT_TYPE']
            # Desde Low(-1) a High(1) = tramo alcista(1), desde High(1) a Low(-1) = tramo bajista(-1)
            direction = -ptype_start  # Low→High = +1, High→Low = -1
            df.loc[idx_start:idx_end, 'ZIGZAG_DIRECTION'] = direction
        
        return df

    def detectar_divergencias(self, df, col_indicador, nombre_salida_base='DIV'):
        """
        Detecta TODAS las divergencias (Regulares y Ocultas) clasificadas por Tipo (A y B).
        
        Salidas generadas:
        1. REGULAR_A: Cambio de tendencia fuerte (Inclinada).
        2. REGULAR_B: Cambio de tendencia en Doble Suelo/Techo (Plana).
        3. OCULTA_A:  Continuación de tendencia fuerte (Inclinada).
        4. OCULTA_B:  Continuación de tendencia en Doble Suelo/Techo (Plana).
        """
        from backtests.enbolsa.divergencia_numba import calc_divergencias_numba

        ind_tolerance = 0.0 # Default
        
        if 'RSI' in col_indicador or 'STOCH_K' in col_indicador:
            # Escala 0-100: Pedimos al menos 1 punto de diferencia para evitar ruido
            ind_tolerance = 1.0 
            
        elif 'EWO' in col_indicador or 'MACD_HISTOGRAMA' in col_indicador:
            # Escala decimal pequeña (Forex) o grande (BTC).
            # Para Forex (EURUSD), el EWO se mueve en 0.001 - 0.005.
            # Usaremos 0.0001 como filtro de ruido mínimo.
            ind_tolerance = 0.0001
        
        # Preparar arrays para Numba
        # Aseguramos tipos correctos. fillna(0) para pivots por si acaso.
        prices = df['close'].values.astype(np.float64)
        # Rellenamos NaN en indicadores para evitar problemas en Numba
        indicators = df[col_indicador].fillna(0).values.astype(np.float64)
        pivot_types = df['PIVOT_TYPE'].fillna(0).values.astype(np.int64)

        # Llamada a función optimizada
        reg_a, reg_b, ocult_a, ocult_b = calc_divergencias_numba(
            prices, indicators, pivot_types, self.tolerance, ind_tolerance
        )

        # Asignar resultados al DataFrame
        df[f'{nombre_salida_base}_{col_indicador}_REGULAR_A'] = reg_a
        df[f'{nombre_salida_base}_{col_indicador}_REGULAR_B'] = reg_b
        df[f'{nombre_salida_base}_{col_indicador}_OCULTA_A'] = ocult_a
        df[f'{nombre_salida_base}_{col_indicador}_OCULTA_B'] = ocult_b

        return df

    def calcular_proyecciones_fibonacci(self, df):
        """
        Calcula Proyecciones (Expansion) y Retrocesos basados en la estructura ZigZag.
        Incluye niveles clave de Elliott: Retrocesos 38.2%, 50%, 61.8% y Objetivos 100%, 138.2%, 161.8%.
        
        CORRECCIÓN LÓGICA:
        - Los RETROCESOS se dibujan en el tramo ACTUAL pero se calculan basados en el tramo ANTERIOR. 
          (Ej: Si estoy bajando, quiero ver los niles de fibo de la subida anterior).
        - Las PROYECCIONES se dibujan en el tramo ACTUAL (Onda 3/5/C) y se basan en la estructura A-B-C previa.
        """
        return self._calcular_proyecciones_fibonacci_fast(df)

        # 1. Inicializamos columnas de objetivos con NaN
        # Proyecciones (Targets de Onda 3 o 5)
        df['FIB_TARGET_1.0']   = np.nan  # Igualdad (Onda 5 o ZigZag ABC)
        df['FIB_TARGET_1.382'] = np.nan  # Extension menor
        df['FIB_TARGET_1.618'] = np.nan  # Extension dorada (Onda 3)
        
        # Zonas de Soporte/Resistencia (Retrocesos de Onda 2 o 4)
        df['FIB_RETR_0.382'] = np.nan
        df['FIB_RETR_0.5']   = np.nan    # El 50% clásico
        df['FIB_RETR_0.618'] = np.nan
        df['FIB_RETR_0.8']   = np.nan    # Retroceso profundo 80%

        # Obtenemos índices y valores de los pivotes
        # Filtramos solo donde hay pivote confirmado
        pivots = df[df['PIVOT_TYPE'] != 0].copy()
        indices = pivots.index.tolist()
        types = pivots['PIVOT_TYPE'].values
        values = pivots['PIVOT_VALUE'].values

        if len(indices) < 3:
            return df

        # Recorremos los tramos (Legs)
        # i es el índice del pivote de INICIO del tramo actual
        # i+1 es el índice del pivote de FIN del tramo actual (que se está formando o completó)
        for i in range(len(indices) - 1):
            idx_curr = indices[i]
            idx_next = indices[i+1] 
            
            # --- 1. RETROCESOS (Support/Resist del tramo anterior) ---
            # Para el tramo actual (i -> i+1), los niveles relevantes son los del tramo PREVIO (i-1 -> i)
            if i >= 1:
                val_PrevStart = values[i-1]
                val_PrevEnd   = values[i]
                
                # Calculamos el rango del movimiento anterior
                diff_prev = val_PrevEnd - val_PrevStart
                
                # Los niveles de retroceso se proyectan desde el final del movimiento anterior (val_PrevEnd)
                # hacia abajo (si fue subida) o hacia arriba (si fue bajada).
                # La formula matemática es simple: High - Range*Ratio ó Low + Range*Ratio.
                # Como 'diff_prev' tiene signo, la resta funciona universalmente:
                # Si subió (+100): 200 - (100*0.382) = 161.8 (Soporte abajo)
                # Si bajó (-100):  100 - (-100*0.382) = 100 + 38.2 = 138.2 (Resistencia arriba)
                
                retr_382 = val_PrevEnd - (diff_prev * 0.382)
                retr_500 = val_PrevEnd - (diff_prev * 0.5)
                retr_618 = val_PrevEnd - (diff_prev * 0.618)
                retr_800 = val_PrevEnd - (diff_prev * 0.8)
                
                df.loc[idx_curr:idx_next, 'FIB_RETR_0.382'] = retr_382
                df.loc[idx_curr:idx_next, 'FIB_RETR_0.5']   = retr_500
                df.loc[idx_curr:idx_next, 'FIB_RETR_0.618'] = retr_618
                df.loc[idx_curr:idx_next, 'FIB_RETR_0.8']   = retr_800

            # --- 2. PROYECCIONES (Targets para Onda 3/5/C) ---
            # Necesitamos 3 puntos definidos: Inicio(A), Rebote(B), FinCorreccion(C).
            # El tramo actual es el impulso que sale de C. (i -> i+1 es el tramo post-C).
            # Entonces: A=(i-2), B=(i-1), C=(i).
            if i >= 2:
                val_A = values[i-2] # Inicio Impulso Previo
                val_B = values[i-1] # Fin Impulso Previo
                val_C = values[i]   # Fin Corrección (Inicio Tramo Actual)
                
                type_A = types[i-2]
                type_B = types[i-1]
                type_C = types[i]
                
                # Validamos estructura de impulso/corrección
                # Alcista Total: A(Low)->B(High)->C(Higher Low) -> Proyectamos arriba
                es_impulso_alcista = (type_A == -1) and (type_B == 1) and (type_C == -1)
                # Bajista Total: A(High)->B(Low)->C(Lower High) -> Proyectamos abajo
                es_impulso_bajista = (type_A == 1) and (type_B == -1) and (type_C == 1)
                
                if es_impulso_alcista or es_impulso_bajista:
                    # Altura del impulso previo (A->B)
                    altura_impulso = abs(val_B - val_A)
                    
                    if es_impulso_alcista:
                        target_100 = val_C + (altura_impulso * 1.0)
                        target_138 = val_C + (altura_impulso * 1.382)
                        target_161 = val_C + (altura_impulso * 1.618)
                    else: # Bajista
                        target_100 = val_C - (altura_impulso * 1.0)
                        target_138 = val_C - (altura_impulso * 1.382)
                        target_161 = val_C - (altura_impulso * 1.618)
                    
                    df.loc[idx_curr:idx_next, 'FIB_TARGET_1.0']   = target_100
                    df.loc[idx_curr:idx_next, 'FIB_TARGET_1.382'] = target_138
                    df.loc[idx_curr:idx_next, 'FIB_TARGET_1.618'] = target_161

        # Rellenamos los huecos hacia adelante (Forward Fill) para tener los niveles activos hasta que cambien
        cols_fib = [
            'FIB_TARGET_1.0', 'FIB_TARGET_1.382', 'FIB_TARGET_1.618', 
            'FIB_RETR_0.382', 'FIB_RETR_0.5', 'FIB_RETR_0.618', 'FIB_RETR_0.8'
        ]
        df[cols_fib] = df[cols_fib].ffill()
        
        return df

    def _calcular_proyecciones_fibonacci_fast(self, df):
        size = len(df)
        fib_arrays = {
            'FIB_TARGET_1.0': np.full(size, np.nan),
            'FIB_TARGET_1.382': np.full(size, np.nan),
            'FIB_TARGET_1.618': np.full(size, np.nan),
            'FIB_RETR_0.382': np.full(size, np.nan),
            'FIB_RETR_0.5': np.full(size, np.nan),
            'FIB_RETR_0.618': np.full(size, np.nan),
            'FIB_RETR_0.8': np.full(size, np.nan),
        }

        pivot_types_full = df['PIVOT_TYPE'].fillna(0).astype(int).to_numpy()
        pivot_values_full = df['PIVOT_VALUE'].to_numpy(dtype=float)
        pivot_positions = np.flatnonzero(pivot_types_full != 0)

        if len(pivot_positions) < 2:
            for col, values in fib_arrays.items():
                df[col] = values
            return df

        types = pivot_types_full[pivot_positions]
        values = pivot_values_full[pivot_positions]

        for i in range(len(pivot_positions) - 1):
            start = int(pivot_positions[i])
            stop = int(pivot_positions[i + 1]) + 1

            if i >= 1:
                val_prev_start = values[i - 1]
                val_prev_end = values[i]
                diff_prev = val_prev_end - val_prev_start

                fib_arrays['FIB_RETR_0.382'][start:stop] = val_prev_end - (diff_prev * 0.382)
                fib_arrays['FIB_RETR_0.5'][start:stop] = val_prev_end - (diff_prev * 0.5)
                fib_arrays['FIB_RETR_0.618'][start:stop] = val_prev_end - (diff_prev * 0.618)
                fib_arrays['FIB_RETR_0.8'][start:stop] = val_prev_end - (diff_prev * 0.8)

            if i >= 2:
                val_A = values[i - 2]
                val_B = values[i - 1]
                val_C = values[i]

                type_A = types[i - 2]
                type_B = types[i - 1]
                type_C = types[i]

                es_impulso_alcista = (type_A == -1) and (type_B == 1) and (type_C == -1)
                es_impulso_bajista = (type_A == 1) and (type_B == -1) and (type_C == 1)

                if es_impulso_alcista or es_impulso_bajista:
                    altura_impulso = abs(val_B - val_A)

                    if es_impulso_alcista:
                        fib_arrays['FIB_TARGET_1.0'][start:stop] = val_C + (altura_impulso * 1.0)
                        fib_arrays['FIB_TARGET_1.382'][start:stop] = val_C + (altura_impulso * 1.382)
                        fib_arrays['FIB_TARGET_1.618'][start:stop] = val_C + (altura_impulso * 1.618)
                    else:
                        fib_arrays['FIB_TARGET_1.0'][start:stop] = val_C - (altura_impulso * 1.0)
                        fib_arrays['FIB_TARGET_1.382'][start:stop] = val_C - (altura_impulso * 1.382)
                        fib_arrays['FIB_TARGET_1.618'][start:stop] = val_C - (altura_impulso * 1.618)

        for col, values in fib_arrays.items():
            df[col] = pd.Series(values, index=df.index).ffill()

        return df

    def _inicializar_columnas_setup(self, df):
        nan_cols = [
            'LONG_W1_START_PRICE', 'LONG_W1_END_PRICE', 'LONG_W1_SIZE',
            'LONG_W2_EXTREME_PRICE', 'LONG_W2_RETR_PCT', 'LONG_W2_SWING_PRICE',
            'LONG_FIB_LEVEL_0.5', 'LONG_FIB_LEVEL_0.618', 'LONG_FIB_LEVEL_0.8',
            'LONG_TARGET_1.0', 'LONG_TARGET_1.618',
            'SHORT_W1_START_PRICE', 'SHORT_W1_END_PRICE', 'SHORT_W1_SIZE',
            'SHORT_W2_EXTREME_PRICE', 'SHORT_W2_RETR_PCT', 'SHORT_W2_SWING_PRICE',
            'SHORT_FIB_LEVEL_0.5', 'SHORT_FIB_LEVEL_0.618', 'SHORT_FIB_LEVEL_0.8',
            'SHORT_TARGET_1.0', 'SHORT_TARGET_1.618',
            'W1_START_PRICE', 'W1_END_PRICE', 'W1_SIZE',
            'W2_EXTREME_PRICE', 'W2_RETR_PCT',
            'LONG_SETUP_AGE', 'SHORT_SETUP_AGE', 'SETUP_AGE'
        ]
        bool_cols = [
            'LONG_SETUP_ACTIVE', 'LONG_W2_VALID_80', 'LONG_W2_INVALIDATED',
            'LONG_W2_TRENDLINE_BROKEN', 'LONG_FIB_TOUCH_618',
            'SHORT_SETUP_ACTIVE', 'SHORT_W2_VALID_80', 'SHORT_W2_INVALIDATED',
            'SHORT_W2_TRENDLINE_BROKEN', 'SHORT_FIB_TOUCH_618',
            'W2_VALID_80', 'W2_INVALIDATED', 'W2_TRENDLINE_BROKEN', 'FIB_TOUCH_618'
        ]

        for col in nan_cols:
            df[col] = np.nan
        for col in bool_cols:
            df[col] = False

        df['LONG_SETUP_ID'] = 0
        df['SHORT_SETUP_ID'] = 0
        df['SETUP_ID'] = 0
        df['SETUP_DIR'] = 0
        return df

    def _calc_trendline_break(self, trendline_values, closes, anchor_pos, current_pos, direction):
        bars = current_pos - anchor_pos
        if bars < 3:
            return False

        window = trendline_values[anchor_pos:current_pos]
        if len(window) < 3 or np.isnan(window).any():
            return False

        x_prev = np.arange(len(window), dtype=float)
        slope, intercept = np.polyfit(x_prev, window, 1)
        prev_line = intercept + slope * (len(window) - 1)
        curr_line = intercept + slope * len(window)
        prev_close = closes[current_pos - 1]
        curr_close = closes[current_pos]

        if direction == 1:
            return slope < 0 and prev_close <= prev_line and curr_close > curr_line
        return slope > 0 and prev_close >= prev_line and curr_close < curr_line

    def _volcar_setup(self, df, row_pos, setup, prefix, lows, highs, closes):
        idx = df.index[row_pos]
        direction = setup['direction']
        w1_start = float(setup['start_price'])
        w1_end = float(setup['end_price'])
        w1_size = abs(w1_end - w1_start)

        if direction == 1:
            w2_extreme = float(np.nanmin(lows[setup['anchor_pos']:row_pos + 1]))
            retr_pct = (w1_end - w2_extreme) / w1_size if w1_size > 0 else np.nan
            invalidated = bool(w2_extreme <= w1_start)
            fib_500 = w1_end - (w1_size * 0.5)
            fib_618 = w1_end - (w1_size * 0.618)
            fib_800 = w1_end - (w1_size * 0.8)
            fib_touch = bool(lows[row_pos] <= fib_618 <= highs[row_pos])
            target_100 = w2_extreme + w1_size
            target_1618 = w2_extreme + (w1_size * 1.618)
        else:
            w2_extreme = float(np.nanmax(highs[setup['anchor_pos']:row_pos + 1]))
            retr_pct = (w2_extreme - w1_end) / w1_size if w1_size > 0 else np.nan
            invalidated = bool(w2_extreme >= w1_start)
            fib_500 = w1_end + (w1_size * 0.5)
            fib_618 = w1_end + (w1_size * 0.618)
            fib_800 = w1_end + (w1_size * 0.8)
            fib_touch = bool(lows[row_pos] <= fib_618 <= highs[row_pos])
            target_100 = w2_extreme - w1_size
            target_1618 = w2_extreme - (w1_size * 1.618)

        trendline_broken = self._calc_trendline_break(
            highs if direction == 1 else lows, closes, setup['anchor_pos'], row_pos, direction
        )
        w2_valid_80 = bool((retr_pct <= 0.8) and not invalidated)

        df.at[idx, f'{prefix}_SETUP_ID'] = setup['id']
        df.at[idx, f'{prefix}_SETUP_ACTIVE'] = True
        df.at[idx, f'{prefix}_SETUP_AGE'] = row_pos - setup['created_pos']
        df.at[idx, f'{prefix}_W1_START_PRICE'] = w1_start
        df.at[idx, f'{prefix}_W1_END_PRICE'] = w1_end
        df.at[idx, f'{prefix}_W1_SIZE'] = w1_size
        df.at[idx, f'{prefix}_W2_EXTREME_PRICE'] = w2_extreme
        df.at[idx, f'{prefix}_W2_RETR_PCT'] = retr_pct
        df.at[idx, f'{prefix}_W2_SWING_PRICE'] = setup['swing_price']
        df.at[idx, f'{prefix}_W2_VALID_80'] = w2_valid_80
        df.at[idx, f'{prefix}_W2_INVALIDATED'] = invalidated
        df.at[idx, f'{prefix}_FIB_LEVEL_0.5'] = fib_500
        df.at[idx, f'{prefix}_FIB_LEVEL_0.618'] = fib_618
        df.at[idx, f'{prefix}_FIB_LEVEL_0.8'] = fib_800
        df.at[idx, f'{prefix}_FIB_TOUCH_618'] = fib_touch
        df.at[idx, f'{prefix}_W2_TRENDLINE_BROKEN'] = trendline_broken
        df.at[idx, f'{prefix}_TARGET_1.0'] = target_100
        df.at[idx, f'{prefix}_TARGET_1.618'] = target_1618

    def detectar_setups_enbolsa(self, df):
        """
        Construye el setup operativo W1 -> W2 -> W3 sin look-ahead bias.
        """
        return self._detectar_setups_enbolsa_fast(df)

        df = self._inicializar_columnas_setup(df)

        pivot_types = df['PIVOT_TYPE'].fillna(0).astype(int).values
        pivot_values = df['PIVOT_VALUE'].values.astype(float)
        lows = df['low'].values.astype(float)
        highs = df['high'].values.astype(float)
        closes = df['close'].values.astype(float)

        last_low = None
        last_high = None
        long_setup = None
        short_setup = None
        long_setup_id = 0
        short_setup_id = 0

        for row_pos, pivot_type in enumerate(pivot_types):
            pivot_value = pivot_values[row_pos]

            if pivot_type == 1 and last_low is not None and not np.isnan(pivot_value):
                long_setup_id += 1
                long_setup = {
                    'id': long_setup_id,
                    'direction': 1,
                    'start_price': last_low['price'],
                    'end_price': pivot_value,
                    'anchor_pos': row_pos,
                    'created_pos': row_pos,
                    'swing_price': np.nan,
                }

            if pivot_type == -1 and last_high is not None and not np.isnan(pivot_value):
                short_setup_id += 1
                short_setup = {
                    'id': short_setup_id,
                    'direction': -1,
                    'start_price': last_high['price'],
                    'end_price': pivot_value,
                    'anchor_pos': row_pos,
                    'created_pos': row_pos,
                    'swing_price': np.nan,
                }

            if pivot_type == -1 and long_setup is not None and row_pos >= long_setup['anchor_pos']:
                long_setup['swing_price'] = pivot_value
            if pivot_type == 1 and short_setup is not None and row_pos >= short_setup['anchor_pos']:
                short_setup['swing_price'] = pivot_value

            if pivot_type == -1 and not np.isnan(pivot_value):
                last_low = {'price': pivot_value, 'pos': row_pos}
            if pivot_type == 1 and not np.isnan(pivot_value):
                last_high = {'price': pivot_value, 'pos': row_pos}

            if long_setup is not None:
                self._volcar_setup(df, row_pos, long_setup, 'LONG', lows, highs, closes)
            if short_setup is not None:
                self._volcar_setup(df, row_pos, short_setup, 'SHORT', lows, highs, closes)

            idx = df.index[row_pos]
            candidates = []
            if long_setup is not None:
                candidates.append((long_setup['created_pos'], 'LONG', 1))
            if short_setup is not None:
                candidates.append((short_setup['created_pos'], 'SHORT', -1))

            if candidates:
                _, prefix, direction = max(candidates, key=lambda item: item[0])
                df.at[idx, 'SETUP_ID'] = df.at[idx, f'{prefix}_SETUP_ID']
                df.at[idx, 'SETUP_DIR'] = direction
                df.at[idx, 'SETUP_AGE'] = df.at[idx, f'{prefix}_SETUP_AGE']
                df.at[idx, 'W1_START_PRICE'] = df.at[idx, f'{prefix}_W1_START_PRICE']
                df.at[idx, 'W1_END_PRICE'] = df.at[idx, f'{prefix}_W1_END_PRICE']
                df.at[idx, 'W1_SIZE'] = df.at[idx, f'{prefix}_W1_SIZE']
                df.at[idx, 'W2_EXTREME_PRICE'] = df.at[idx, f'{prefix}_W2_EXTREME_PRICE']
                df.at[idx, 'W2_RETR_PCT'] = df.at[idx, f'{prefix}_W2_RETR_PCT']
                df.at[idx, 'W2_VALID_80'] = df.at[idx, f'{prefix}_W2_VALID_80']
                df.at[idx, 'W2_INVALIDATED'] = df.at[idx, f'{prefix}_W2_INVALIDATED']
                df.at[idx, 'FIB_TOUCH_618'] = df.at[idx, f'{prefix}_FIB_TOUCH_618']
                df.at[idx, 'W2_TRENDLINE_BROKEN'] = df.at[idx, f'{prefix}_W2_TRENDLINE_BROKEN']

        return df

    def _create_setup_state(self, setup_id, direction, start_price, end_price, anchor_pos):
        return {
            'id': int(setup_id),
            'direction': int(direction),
            'start_price': float(start_price),
            'end_price': float(end_price),
            'w1_size': abs(float(end_price) - float(start_price)),
            'start_pos': int(anchor_pos),
            'anchor_pos': int(anchor_pos),
            'created_pos': int(anchor_pos),
            'swing_price': np.nan,
            'w2_extreme': np.inf if direction == 1 else -np.inf,
            'trend_n': 0,
            'trend_sum_x': 0.0,
            'trend_sum_x2': 0.0,
            'trend_sum_y': 0.0,
            'trend_sum_xy': 0.0,
            'trend_has_nan': False,
        }

    def _append_trendline_point(self, setup, trendline_value):
        x = float(setup['trend_n'])
        setup['trend_n'] += 1

        if np.isnan(trendline_value):
            setup['trend_has_nan'] = True
            return

        setup['trend_sum_x'] += x
        setup['trend_sum_x2'] += x * x
        setup['trend_sum_y'] += float(trendline_value)
        setup['trend_sum_xy'] += x * float(trendline_value)

    def _trendline_break_from_state(self, setup, prev_close, curr_close):
        n = int(setup['trend_n'])
        if n < 3 or setup['trend_has_nan']:
            return False
        if np.isnan(prev_close) or np.isnan(curr_close):
            return False

        sum_x = setup['trend_sum_x']
        sum_x2 = setup['trend_sum_x2']
        sum_y = setup['trend_sum_y']
        sum_xy = setup['trend_sum_xy']
        denom = (n * sum_x2) - (sum_x * sum_x)

        if abs(denom) < 1e-12:
            return False

        slope = ((n * sum_xy) - (sum_x * sum_y)) / denom
        intercept = (sum_y - (slope * sum_x)) / n
        prev_line = intercept + (slope * (n - 1))
        curr_line = intercept + (slope * n)

        if setup['direction'] == 1:
            return slope < 0 and prev_close <= prev_line and curr_close > curr_line
        return slope > 0 and prev_close >= prev_line and curr_close < curr_line

    def _detectar_setups_enbolsa_fast(self, df):
        df = df.copy()
        size = len(df)

        nan_cols = [
            'LONG_W1_START_PRICE', 'LONG_W1_END_PRICE', 'LONG_W1_SIZE',
            'LONG_W2_EXTREME_PRICE', 'LONG_W2_RETR_PCT', 'LONG_W2_SWING_PRICE',
            'LONG_FIB_LEVEL_0.5', 'LONG_FIB_LEVEL_0.618', 'LONG_FIB_LEVEL_0.8',
            'LONG_TARGET_1.0', 'LONG_TARGET_1.618',
            'SHORT_W1_START_PRICE', 'SHORT_W1_END_PRICE', 'SHORT_W1_SIZE',
            'SHORT_W2_EXTREME_PRICE', 'SHORT_W2_RETR_PCT', 'SHORT_W2_SWING_PRICE',
            'SHORT_FIB_LEVEL_0.5', 'SHORT_FIB_LEVEL_0.618', 'SHORT_FIB_LEVEL_0.8',
            'SHORT_TARGET_1.0', 'SHORT_TARGET_1.618',
            'W1_START_PRICE', 'W1_END_PRICE', 'W1_SIZE',
            'W2_EXTREME_PRICE', 'W2_RETR_PCT',
        ]
        bool_cols = [
            'LONG_SETUP_ACTIVE', 'LONG_W2_VALID_80', 'LONG_W2_INVALIDATED',
            'LONG_W2_TRENDLINE_BROKEN', 'LONG_FIB_TOUCH_618',
            'SHORT_SETUP_ACTIVE', 'SHORT_W2_VALID_80', 'SHORT_W2_INVALIDATED',
            'SHORT_W2_TRENDLINE_BROKEN', 'SHORT_FIB_TOUCH_618',
            'W2_VALID_80', 'W2_INVALIDATED', 'W2_TRENDLINE_BROKEN', 'FIB_TOUCH_618',
        ]
        int_cols = [
            'LONG_SETUP_ID', 'SHORT_SETUP_ID', 'SETUP_ID', 'SETUP_DIR',
            'LONG_SETUP_AGE', 'SHORT_SETUP_AGE', 'SETUP_AGE',
            'LONG_W1_BARS', 'SHORT_W1_BARS', 'W1_BARS',
        ]

        out = {col: np.full(size, np.nan) for col in nan_cols}
        out.update({col: np.zeros(size, dtype=bool) for col in bool_cols})
        out.update({col: np.zeros(size, dtype=int) for col in int_cols})

        pivot_types = df['PIVOT_TYPE'].fillna(0).astype(int).to_numpy()
        pivot_values = df['PIVOT_VALUE'].to_numpy(dtype=float)
        lows = df['low'].to_numpy(dtype=float)
        highs = df['high'].to_numpy(dtype=float)
        closes = df['close'].to_numpy(dtype=float)

        last_low = None
        last_high = None
        long_setup = None
        short_setup = None
        long_setup_id = 0
        short_setup_id = 0

        def _write_setup(row_pos, setup, prefix):
            w1_start = setup['start_price']
            w1_end = setup['end_price']
            w1_size = setup['w1_size']

            if setup['direction'] == 1:
                if not np.isnan(lows[row_pos]):
                    setup['w2_extreme'] = min(setup['w2_extreme'], float(lows[row_pos]))
                w2_extreme = float(setup['w2_extreme'])
                retr_pct = (w1_end - w2_extreme) / w1_size if w1_size > 0 else np.nan
                invalidated = bool(w2_extreme <= w1_start)
                fib_500 = w1_end - (w1_size * 0.5)
                fib_618 = w1_end - (w1_size * 0.618)
                fib_800 = w1_end - (w1_size * 0.8)
                target_100 = w2_extreme + w1_size
                target_1618 = w2_extreme + (w1_size * 1.618)
            else:
                if not np.isnan(highs[row_pos]):
                    setup['w2_extreme'] = max(setup['w2_extreme'], float(highs[row_pos]))
                w2_extreme = float(setup['w2_extreme'])
                retr_pct = (w2_extreme - w1_end) / w1_size if w1_size > 0 else np.nan
                invalidated = bool(w2_extreme >= w1_start)
                fib_500 = w1_end + (w1_size * 0.5)
                fib_618 = w1_end + (w1_size * 0.618)
                fib_800 = w1_end + (w1_size * 0.8)
                target_100 = w2_extreme - w1_size
                target_1618 = w2_extreme - (w1_size * 1.618)

            fib_touch = bool(
                not np.isnan(fib_618) and
                not np.isnan(lows[row_pos]) and
                not np.isnan(highs[row_pos]) and
                lows[row_pos] <= fib_618 <= highs[row_pos]
            )
            trendline_broken = self._trendline_break_from_state(
                setup,
                closes[row_pos - 1] if row_pos > 0 else np.nan,
                closes[row_pos],
            )
            w2_valid_80 = bool((retr_pct <= 0.8) and not invalidated)
            age = row_pos - setup['created_pos']

            out[f'{prefix}_SETUP_ID'][row_pos] = setup['id']
            out[f'{prefix}_SETUP_ACTIVE'][row_pos] = True
            out[f'{prefix}_SETUP_AGE'][row_pos] = age
            out[f'{prefix}_W1_START_PRICE'][row_pos] = w1_start
            out[f'{prefix}_W1_END_PRICE'][row_pos] = w1_end
            out[f'{prefix}_W1_SIZE'][row_pos] = w1_size
            out[f'{prefix}_W1_BARS'][row_pos] = max(0, setup['anchor_pos'] - setup['start_pos'])
            out[f'{prefix}_W2_EXTREME_PRICE'][row_pos] = w2_extreme
            out[f'{prefix}_W2_RETR_PCT'][row_pos] = retr_pct
            out[f'{prefix}_W2_SWING_PRICE'][row_pos] = setup['swing_price']
            out[f'{prefix}_W2_VALID_80'][row_pos] = w2_valid_80
            out[f'{prefix}_W2_INVALIDATED'][row_pos] = invalidated
            out[f'{prefix}_FIB_LEVEL_0.5'][row_pos] = fib_500
            out[f'{prefix}_FIB_LEVEL_0.618'][row_pos] = fib_618
            out[f'{prefix}_FIB_LEVEL_0.8'][row_pos] = fib_800
            out[f'{prefix}_FIB_TOUCH_618'][row_pos] = fib_touch
            out[f'{prefix}_W2_TRENDLINE_BROKEN'][row_pos] = trendline_broken
            out[f'{prefix}_TARGET_1.0'][row_pos] = target_100
            out[f'{prefix}_TARGET_1.618'][row_pos] = target_1618

            trendline_source_value = highs[row_pos] if setup['direction'] == 1 else lows[row_pos]
            self._append_trendline_point(setup, trendline_source_value)

        for row_pos, pivot_type in enumerate(pivot_types):
            pivot_value = pivot_values[row_pos]

            if pivot_type == 1 and last_low is not None and not np.isnan(pivot_value):
                long_setup_id += 1
                long_setup = self._create_setup_state(
                    long_setup_id, 1, last_low['price'], pivot_value, row_pos
                )
                long_setup['start_pos'] = last_low['pos']

            if pivot_type == -1 and last_high is not None and not np.isnan(pivot_value):
                short_setup_id += 1
                short_setup = self._create_setup_state(
                    short_setup_id, -1, last_high['price'], pivot_value, row_pos
                )
                short_setup['start_pos'] = last_high['pos']

            if pivot_type == -1 and long_setup is not None and row_pos >= long_setup['anchor_pos']:
                long_setup['swing_price'] = pivot_value
            if pivot_type == 1 and short_setup is not None and row_pos >= short_setup['anchor_pos']:
                short_setup['swing_price'] = pivot_value

            if pivot_type == -1 and not np.isnan(pivot_value):
                last_low = {'price': float(pivot_value), 'pos': row_pos}
            if pivot_type == 1 and not np.isnan(pivot_value):
                last_high = {'price': float(pivot_value), 'pos': row_pos}

            if long_setup is not None:
                _write_setup(row_pos, long_setup, 'LONG')
            if short_setup is not None:
                _write_setup(row_pos, short_setup, 'SHORT')

            candidates = []
            if long_setup is not None:
                candidates.append((long_setup['created_pos'], 'LONG', 1))
            if short_setup is not None:
                candidates.append((short_setup['created_pos'], 'SHORT', -1))

            if candidates:
                _, prefix, direction = max(candidates, key=lambda item: item[0])
                out['SETUP_ID'][row_pos] = out[f'{prefix}_SETUP_ID'][row_pos]
                out['SETUP_DIR'][row_pos] = direction
                out['SETUP_AGE'][row_pos] = out[f'{prefix}_SETUP_AGE'][row_pos]
                out['W1_START_PRICE'][row_pos] = out[f'{prefix}_W1_START_PRICE'][row_pos]
                out['W1_END_PRICE'][row_pos] = out[f'{prefix}_W1_END_PRICE'][row_pos]
                out['W1_SIZE'][row_pos] = out[f'{prefix}_W1_SIZE'][row_pos]
                out['W1_BARS'][row_pos] = out[f'{prefix}_W1_BARS'][row_pos]
                out['W2_EXTREME_PRICE'][row_pos] = out[f'{prefix}_W2_EXTREME_PRICE'][row_pos]
                out['W2_RETR_PCT'][row_pos] = out[f'{prefix}_W2_RETR_PCT'][row_pos]
                out['W2_VALID_80'][row_pos] = out[f'{prefix}_W2_VALID_80'][row_pos]
                out['W2_INVALIDATED'][row_pos] = out[f'{prefix}_W2_INVALIDATED'][row_pos]
                out['FIB_TOUCH_618'][row_pos] = out[f'{prefix}_FIB_TOUCH_618'][row_pos]
                out['W2_TRENDLINE_BROKEN'][row_pos] = out[f'{prefix}_W2_TRENDLINE_BROKEN'][row_pos]

        for col, values in out.items():
            df[col] = values

        return df

    def procesar_contexto_completo(self, df, lista_indicadores=['RSI', 'EWO', 'STOCH_K']):
        """
        Ejecuta la cadena completa: Tendencia -> ZigZag -> Fibonacci -> Divergencias Múltiples.
        Este es el método que debes llamar desde tu script principal.
        """
        # 1. Calcular Estructura Base
        df = self.calcular_tendencia(df)
        df = self.calcular_zigzag(df)
        
        # 1b. Confirmar pivotes sin Look-Ahead Bias
        #     Desplaza cada pivot al bar donde se confirma en tiempo real.
        df = self._confirmar_pivotes(df)
        
        # 2. Calcular Niveles de Fibonacci (Soportes/Resistencia y Objetivos)
        #    Ahora usa pivotes confirmados → sin sesgo.
        df = self.calcular_proyecciones_fibonacci(df)
        df = self.detectar_setups_enbolsa(df)
        
        # 3. Calcular Divergencias para cada indicador
        for indicador in lista_indicadores:
            if indicador in df.columns:
                df = self.detectar_divergencias(df, col_indicador=indicador, 
                                              nombre_salida_base='DIV')
            
            
        return df

    def sincronizar_tendencia_htf(self, df_ltf, df_htf, suffix='_HTF'):
        """
        Calcula la tendencia en el DF de temporalidad superior (HTF) y la fusiona
        con el DF de temporalidad inferior (LTF) sin Look-Ahead Bias.

        Args:
            df_ltf (pd.DataFrame): DataFrame de temporalidad baja (ej. 1H). Debe tener índice Datetime.
            df_htf (pd.DataFrame): DataFrame de temporalidad alta (ej. 4H). Debe tener índice Datetime.
            suffix (str): Sufijo para la columna (ej. '_4H' -> 'TENDENCIA_ESTRUCTURAL_4H').
        
        Returns:
            df_ltf con la nueva columna añadida.
        """
        # 1. Calcular Tendencia en HTF
        # Usamos una instancia temporal o la misma lógica
        df_htf = self.calcular_tendencia(df_htf)
        
        # 2. Prevenir Look-Ahead Bias con SHIFT(1)
        # La vela de las 12:00 de H4 solo se conoce A PARTIR de las 12:00.
        # Por tanto, las velas de M15 de 08:15, 08:30... deben tener la info de la vela H4 de las 08:00 (que cerró a las 08:00, o abrió a las 04:00?)
        # Convención estándar: Timestamp es APERTURA.
        # H4 Candle 08:00 cubre 08:00 - 12:00. Cierra a las 12:00.
        # M15 Candle 08:15 ocurre DURANTE la vela H4 de 08:00.
        # ¿Qué tendencia conoce? La de la vela H4 ANTERIOR (04:00-08:00).
        # Por tanto, a las 08:XX le corresponde el valor de la vela H4 de 04:00.
        # La vela H4 de 04:00 está en el índice 04:00.
        # Si hacemos reindex 'ffill' de 08:00 -> cogerá el valor del índice 08:00 (que es la vela actual no cerrada).
        # Por eso necesitamos SHIFT(1).
        # Al hacer shift(1), en el índice 08:00 ponemos el valor de 04:00.
        # Al hacer ffill en 08:15, coge el índice 08:00 (que ahora tiene el valor de 04:00). CORRECTO.
        
        trend_series = df_htf[['TENDENCIA_ESTRUCTURAL']].shift(1)
        trend_series.columns = [f'TENDENCIA_ESTRUCTURAL{suffix}']
        
        # 3. Merge / Reindex
        # Usamos reindex con method='ffill' para propagar el último valor válido hacia adelante
        # Aseguramos que ambos índices sean datetime y estén ordenados
        if not isinstance(df_ltf.index, pd.DatetimeIndex) or not isinstance(df_htf.index, pd.DatetimeIndex):
            raise ValueError("Ambos DataFrames deben tener índice DatetimeIndex")
            
        trend_reindexed = trend_series.reindex(df_ltf.index, method='ffill')
        
        # Asignación directa de columna (sobreescribe si existe) en lugar de join
        # Esto evita el error "columns overlap" si se ejecuta varias veces
        col_name = f'TENDENCIA_ESTRUCTURAL{suffix}'
        # df_ltf = df_ltf.join(trend_reindexed) # <-- Problema
        
        # Solución: Asignar directamente la Serie
        df_ltf[col_name] = trend_reindexed[col_name]
        
        return df_ltf

