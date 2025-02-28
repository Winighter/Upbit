# Exponential Moving Average (지수 이동 평균)
class Ema:

    def ema(_src:list, _length:int, _array:int = 0):

        l = _length*2 - 1
        if len(_src) < l:
            return
        else:
            '''
            The default sorting is the recent. 
            ex) _src = [latest price,,,past price]
            but i need earliest method
            if you need don't use _src.reverse()
            '''
            _src = _src[0:l]
            _src.reverse()
            ema_list = []

            for i in range(len(_src)):
                if i == 0:
                    ema_list.append(_src[0])
                    
                if i > 0:
                    alpha = round(2 / (_length + 1), 3)
                    ema = round((_src[i] * alpha) + (ema_list[i-1] * (1-alpha)),3)
                    ema_list.append(ema)
            
            ema_list.reverse()
            result = round(ema_list[_array],2)

            return result