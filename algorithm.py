from typing import Any

def determine_severity(row: dict[str, Any]) -> int:
    """
    Алгоритм определения степени критичности дефекта согласно методике

    Args:
        row (dict[str, Any]): строка, возвращаемая запросом

    Returns:
        int: степень критичности дефекта от 1 до 3
    """

    # Код написан так, чтобы его было легко сверять с методикой определения степени критичности дефекта
    # Его можно переписать, но не стоит, т.к. это затруднит отладку и поддержку

    t_max = row.get("t_max") or 0                            # наибольшая допустимая температура для данного вида контрольной точки
    t_sticker = row.get("t_sticker_min") or 0                # показания ТИН, извлекаются из текстового поля
    t_observed = row.get("t_observed") or 0                  # показания тепловизора
    t_similar_unit = row.get("t_similar_unit") or 0          # температура аналогичного узла
    is_attention_required = row["is_attention_required"]     # флаг "требует внимания"
    nominal_current = row.get("nominal_current", 1) or 0     # номинальный ток
    measured_current = row.get("measured_current", 1) or 0   # измереный ток

    # отношение измереного тока к номинальному
    # Если номинальный ток неизвестен, считаем, что он равен измереному
    current_ratio =  measured_current / nominal_current if nominal_current > 0 else 1

    # превышение наибольшей допустимой температуры:
    t_excess = max(t_sticker, t_observed) - t_max            

    # превышение наибольшей допустимой температуры приведенное к номинальному току:
    t_excess_100 = (t_observed - t_max) * current_ratio ** 2

    # Тепловая аномалия она же избыточная температура:
    t_anomaly = (t_observed - t_similar_unit) if t_similar_unit else 0  

    # избыточная температура, приведенная к полуноминальному току:
    t_anomaly_50 = (t_anomaly) * (0.5 * current_ratio) ** 2


    if row["is_panel"] == 'MOTOR':

        ### Электродвигатели ################################################################################
        
        defect_type_short_name = row["defect_type_short_name"] 
        

        ### ДЕФЕКТЫ 1 КАТЕГОРИИ ###

        if defect_type_short_name == "Качение" and max(t_sticker, t_observed) >= 110:
           return 1
        if defect_type_short_name == "Скольжение" and max(t_sticker, t_observed) >= 80:
           return 1
        if t_anomaly >= 15:
            return 1

         ### ДЕФЕКТЫ 2 КАТЕГОРИИ ###

        if defect_type_short_name == "Качение" and 110 > max(t_sticker, t_observed) >= 80:
           return 2
        if defect_type_short_name == "Скольжение" and 80 > max(t_sticker, t_observed) >= 70:
           return 2
        if 15 > t_anomaly > 0:
            return 2

        ### ДЕФЕКТЫ 3 КАТЕГОРИИ ###
        # Все остальное
        return 3

    else:  

        ### Распределительные устройства ###################################################################
        
        is_KRU = ("КРУ" in row["equipment_type_name"])    # Распределительное устройство или ячейка КРУ ?

        ### ДЕФЕКТЫ 1 КАТЕГОРИИ ###

        # дефекты распределительных устройств, для которых:
        #    - измеренная тепловизором температура превышает наибольшую допустимую на 30 ℃ и выше;
        #    - температура, зафиксированная термоиндикатором превышает наибольшую допустимую на 30 ℃ и выше;
        if not is_KRU and t_excess > 30:
            return 1

        # - контактные соединения КРУ или разделка кабельной муфты 6 кВ и выше, или вывод трансформатора, имеющий нагрев выше 80 ℃;
        if is_KRU and t_excess > 80:
            return 1
        
        # - другие дефекты «Требующие внимания»;
        if is_attention_required:    
            return 1

        # - узел попадает в группу «Высокий риск отгорания контакта с ростом тока нагрузки»:
        if current_ratio > 0.6:
            # значение С ≥ 150
            if t_excess + 40 - t_max >= 150:
                return 1
            # значение D ≥ 150
            if t_excess_100 + 40 - t_max >= 150:
                return 1
        # значение E ≥ 200    
        if current_ratio > 0.3 and t_anomaly_50 - 30 >= 200:
            return 1
        # значение F > 30
        if current_ratio >= 0 and t_excess > 30:
            return 1

        ### ДЕФЕКТЫ 2 КАТЕГОРИИ ###

        # - измеренная тепловизором температура превышает наибольшую допустимую не более чем на 30 ℃;
        # - температура, зафиксированная термоиндикатором превышает наибольшую допустимую не более чем на 30 ℃;
        if not is_KRU and 30 >= t_excess > 0:
            return 2

        # - контактные соединения КРУ или разделка кабельной муфты 6 кВ и выше, или вывод трансформатора, имеющий нагрев 70 ÷ 80 ℃.
        if is_KRU and 80 >= t_excess > 70:
            return 2 

        # - температура превышения или температура превышения, приведенная к номинальной нагрузке, 
        # или избыточная температура, приведенная к полуноминальной нагрузке, превышают установленные 
        # наибольшие допустимые температуры;
        if current_ratio > 0.6:
            if t_excess + 40 - t_max >= 0:
                return 2
            if t_excess_100 + 40 - t_max >= 0:
                return 2
        if current_ratio > 0.3 and t_anomaly_50 - 30 >= 0:
            return 2
        if current_ratio >= 0 and t_excess > 0:
            return 2

        ### ДЕФЕКТЫ 3 КАТЕГОРИИ ###
        # Все остальное
        return 3