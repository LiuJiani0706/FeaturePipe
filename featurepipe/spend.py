"""Conservative in-flight reservations plus reported-usage cost estimates.

Prices are explicit run configuration, never a claim about the final invoice.
"""
import threading
import math

from .client import BudgetExceeded


class SpendGuard:
    def __init__(self, maximum, rates):
        if not math.isfinite(maximum) or maximum<=0:raise ValueError('人民币估算预算必须为有限正数')
        self.maximum=maximum;self.rates=rates
        self.spent=0.0;self.held=0.0;self.lock=threading.RLock()

    def reserve(self,model,input_bytes,max_output,protected_remainder=0):
        rate=self.rates[model]
        amount=(input_bytes*rate['input']+max_output*rate['output'])/1000000
        with self.lock:
            if self.spent+self.held+amount>self.maximum-protected_remainder:
                raise BudgetExceeded('人民币估算预算不足以预留下一次请求，已保存结果；不会继续调用')
            self.held+=amount
        return amount

    def finish(self,model,reservation,usage):
        with self.lock:
            if not isinstance(usage,dict) or not all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens')):
                # Unknown billing consumes its full reservation rather than assuming zero.
                self.held-=reservation;self.spent+=reservation
                return
            rate=self.rates[model]
            prompt=usage['prompt_tokens']
            details=usage.get('prompt_tokens_details') or {}
            hit=usage.get('prompt_cache_hit_tokens',details.get('cached_tokens',0))
            hit=min(prompt,max(0,hit if isinstance(hit,int) else 0))
            amount=((prompt-hit)*rate['input']+hit*rate['cached_input']+usage['completion_tokens']*rate['output'])/1000000
            self.held-=reservation;self.spent+=amount

    def cancel(self,reservation):
        with self.lock:self.held-=reservation

    def snapshot(self):
        with self.lock:
            return {'maximum_rmb_estimate':self.maximum,'spent_rmb_estimate':round(self.spent,6),'inflight_rmb_estimate':round(self.held,6),'rates_per_million_tokens':self.rates,
                    'notice':'按配置价格和服务端usage估算，不是账单；未知计费用满预留额。'}

    def restore(self,snapshot):
        with self.lock:
            # Any request still in flight at a crash may have been billed.
            self.spent=snapshot['spent_rmb_estimate']+snapshot.get('inflight_rmb_estimate',0)
            self.held=0.0
