"""
贷款真相计算器 - 核心计算引擎
使用 IRR（内部收益率）法精确计算各类贷款的真实年化利率(APR)
"""

import math
from typing import Optional


def calculate_irr(cash_flows: list[float], tolerance: float = 1e-10, max_iter: int = 1000) -> Optional[float]:
    """
    使用 Newton-Raphson 法计算 IRR（内部收益率）
    
    求解方程: NPV = Σ(CF_i / (1+r)^i) = 0
    
    Args:
        cash_flows: 现金流列表。负数表示支出（到手金额），正数表示收入（还款）
        tolerance: 收敛精度
        max_iter: 最大迭代次数
        
    Returns:
        单期利率 r，如果无法收敛则返回 None
        
    Example:
        借款10000元，分12期每期还900元:
        cash_flows = [-10000, 900, 900, ..., 900]  (共12个900)
        irr = calculate_irr(cash_flows)  # 返回月利率
        apr = irr * 12  # 年化利率
    """
    if not cash_flows or len(cash_flows) < 2:
        return None
    
    # 验证现金流符号必须变化
    positives = [cf for cf in cash_flows if cf > 0]
    negatives = [cf for cf in cash_flows if cf < 0]
    if not positives or not negatives:
        return None
    
    # 使用 Newton-Raphson 迭代
    rate = 0.1  # 初始猜测 10%
    
    for _ in range(max_iter):
        npv = 0.0
        dnpv = 0.0
        
        for i, cf in enumerate(cash_flows):
            factor = (1 + rate) ** i
            npv += cf / factor
            if i > 0:
                dnpv -= i * cf / (factor * (1 + rate))
        
        if abs(dnpv) < 1e-15:
            break
            
        new_rate = rate - npv / dnpv
        
        # 防止发散
        if abs(new_rate) > 10:
            new_rate = rate * 0.5
            
        if abs(new_rate - rate) < tolerance:
            return new_rate
            
        rate = new_rate
    
    # 如果 Newton-Raphson 不收敛，尝试二分法
    return _calculate_irr_bisection(cash_flows, tolerance)


def _calculate_irr_bisection(cash_flows: list[float], tolerance: float = 1e-10) -> Optional[float]:
    """
    二分法求 IRR（Newton-Raphson 失败时的备选方案）
    """
    low, high = -0.99, 10.0  # 利率范围 -99% 到 1000%
    
    for _ in range(200):
        mid = (low + high) / 2
        npv = sum(cf / (1 + mid) ** i for i, cf in enumerate(cash_flows))
        
        if abs(npv) < tolerance:
            return mid
            
        if npv > 0:
            low = mid
        else:
            high = mid
            
        if high - low < tolerance:
            return (low + high) / 2
    
    return None


def calc_equal_principal_interest(principal: float, annual_rate: float, months: int) -> dict:
    """
    等额本息计算
    
    每月还款 = P × r × (1+r)^n / ((1+r)^n - 1)
    其中 r = 月利率 = 年利率 / 12
    
    Returns:
        {
            'monthly_payment': 每月还款额,
            'total_payment': 总还款额,
            'total_interest': 总利息,
            'schedule': 逐期明细列表
        }
    """
    monthly_rate = annual_rate / 12
    n = months
    
    if monthly_rate == 0:
        # 零利率情况
        monthly_payment = principal / n
    else:
        monthly_payment = principal * monthly_rate * (1 + monthly_rate) ** n / \
                         ((1 + monthly_rate) ** n - 1)
    
    schedule = []
    remaining = principal
    
    for i in range(1, n + 1):
        interest_payment = remaining * monthly_rate
        principal_payment = monthly_payment - interest_payment
        
        if i == n:
            # 最后一期调整舍入误差
            principal_payment = remaining
            monthly_payment_final = principal_payment + interest_payment
        else:
            monthly_payment_final = monthly_payment
        
        remaining -= principal_payment
        if remaining < 0:
            remaining = 0
            
        schedule.append({
            'period': i,
            'payment': round(monthly_payment_final, 2),
            'principal': round(principal_payment, 2),
            'interest': round(interest_payment, 2),
            'remaining': round(remaining, 2),
        })
    
    total_payment = sum(s['payment'] for s in schedule)
    total_interest = total_payment - principal
    
    return {
        'monthly_payment': round(monthly_payment, 2),
        'total_payment': round(total_payment, 2),
        'total_interest': round(total_interest, 2),
        'schedule': schedule,
    }


def calc_equal_principal(principal: float, annual_rate: float, months: int) -> dict:
    """
    等额本金计算
    
    每月归还本金相同 = P / n
    每月利息 = 剩余本金 × 月利率
    首月还款最多，逐月递减
    
    Returns:
        {
            'first_month': 首月还款额,
            'last_month': 末月还款额,
            'total_payment': 总还款额,
            'total_interest': 总利息,
            'schedule': 逐期明细列表
        }
    """
    monthly_rate = annual_rate / 12
    monthly_principal = principal / months
    
    schedule = []
    remaining = principal
    total_payment = 0
    
    for i in range(1, months + 1):
        interest_payment = remaining * monthly_rate
        payment = monthly_principal + interest_payment
        remaining -= monthly_principal
        total_payment += payment
        
        if remaining < 0:
            remaining = 0
            
        schedule.append({
            'period': i,
            'payment': round(payment, 2),
            'principal': round(monthly_principal, 2),
            'interest': round(interest_payment, 2),
            'remaining': round(remaining, 2),
        })
    
    total_interest = total_payment - principal
    
    return {
        'first_month': round(schedule[0]['payment'], 2),
        'last_month': round(schedule[-1]['payment'], 2),
        'total_payment': round(total_payment, 2),
        'total_interest': round(total_interest, 2),
        'schedule': schedule,
    }


def calc_interest_first_principal_last(principal: float, annual_rate: float, months: int) -> dict:
    """
    先息后本
    
    每月只还利息，到期一次性还本金
    
    Returns:
        {
            'monthly_interest': 每月利息,
            'final_principal': 到期本金,
            'total_payment': 总还款额,
            'total_interest': 总利息,
            'schedule': 逐期明细
        }
    """
    monthly_rate = annual_rate / 12
    monthly_interest = principal * monthly_rate
    
    schedule = []
    for i in range(1, months + 1):
        if i == months:
            payment = monthly_interest + principal
        else:
            payment = monthly_interest
            
        schedule.append({
            'period': i,
            'payment': round(payment, 2),
            'principal': round(principal if i == months else 0, 2),
            'interest': round(monthly_interest, 2),
            'remaining': round(principal if i < months else 0, 2),
        })
    
    total_interest = monthly_interest * months
    total_payment = principal + total_interest
    
    return {
        'monthly_interest': round(monthly_interest, 2),
        'final_principal': principal,
        'total_payment': round(total_payment, 2),
        'total_interest': round(total_interest, 2),
        'schedule': schedule,
    }


def calc_credit_card_installment(principal: float, monthly_fee_rate: float, months: int) -> dict:
    """
    信用卡分期 / 消费贷（月费率模式）
    
    手续费按借款全额计算，不按剩余本金递减
    这是最经典的"包装利率"套路
    
    Returns:
        {
            'monthly_payment': 每月还款额,
            'monthly_fee': 每月手续费,
            'total_fee': 总手续费,
            'total_payment': 总还款额,
            'apr': 真实年化利率(APR),
            'nominal_rate': 宣传年化（月费率×12）,
            'fee_multiplier': 真实利率/宣传利率的倍数
        }
    """
    monthly_fee = principal * monthly_fee_rate
    monthly_principal = principal / months
    monthly_payment = monthly_principal + monthly_fee
    
    total_fee = monthly_fee * months
    total_payment = principal + total_fee
    
    # 用 IRR 计算真实年化利率
    cash_flows = [-principal] + [monthly_payment] * months
    irr = calculate_irr(cash_flows)
    
    if irr is None:
        return {
            'error': 'IRR 计算失败',
            'monthly_payment': round(monthly_payment, 2),
            'total_fee': round(total_fee, 2),
            'total_payment': round(total_payment, 2),
        }
    
    # 复利年化 APR = (1+irr)^12 - 1
    apr = (1 + irr) ** 12 - 1
    nominal_rate = monthly_fee_rate * 12
    fee_multiplier = apr / nominal_rate if nominal_rate > 0 else float('inf')
    
    schedule = []
    for i in range(1, months + 1):
        schedule.append({
            'period': i,
            'payment': round(monthly_payment, 2),
            'principal': round(monthly_principal, 2),
            'fee': round(monthly_fee, 2),
            'remaining': round(principal - monthly_principal * i, 2),
        })
    
    return {
        'monthly_payment': round(monthly_payment, 2),
        'monthly_fee': round(monthly_fee, 2),
        'total_fee': round(total_fee, 2),
        'total_payment': round(total_payment, 2),
        'apr': round(apr, 4),
        'nominal_rate': round(nominal_rate, 4),
        'fee_multiplier': round(fee_multiplier, 2),
        'schedule': schedule,
    }


def calc_daily_interest_loan(principal: float, daily_rate: float, months: Optional[int] = None,
                              actual_days: Optional[int] = None) -> dict:
    """
    随借随还（按日计息）

    日息万五 = 0.0005 = 年化18.25%

    Args:
        principal: 贷款金额
        daily_rate: 日利率（如万五 = 0.0005）
        months: 预计使用月数（可为None，此时必须提供actual_days）
        actual_days: 实际使用天数。若未提供，按 30×months 估算；
                     若months也未提供，则无法计算，返回error

    Returns:
        {
            'daily_rate': 日利率,
            'apr': 真实年化利率,
            'total_interest': 总利息,
            'monthly_interest': 月均利息（仅当months已知时提供，否则为None）
        }
    """
    if actual_days is None:
        if months is None:
            return {
                'error': '缺少使用天数或使用月数，至少需要其中一项才能计算实际利息',
            }
        actual_days = 30 * months

    apr = daily_rate * 365
    total_interest = principal * daily_rate * actual_days
    monthly_interest = (total_interest / months) if months else None

    return {
        'daily_rate': daily_rate,
        'apr': round(apr, 4),
        'total_interest': round(total_interest, 2),
        'monthly_interest': round(monthly_interest, 2) if monthly_interest is not None else None,
        'actual_days': actual_days,
    }


def calc_head_chopping_loan(contract_amount: float, service_fee_rate: float,
                             monthly_fee_rate: float, months: int) -> dict:
    """
    砍头息贷款
    
    合同金额 > 实际到手金额（服务费前置扣除）
    但利息/手续费按合同金额计算
    
    这是最恶劣的套路之一
    
    Returns:
        {
            'contract_amount': 合同金额,
            'service_fee': 服务费（砍头）,
            'actual_received': 实际到手,
            'monthly_payment': 每月还款,
            'total_payment': 总还款,
            'nominal_apr': 宣传年化,
            'real_apr': 真实年化（IRR）
        }
    """
    service_fee = contract_amount * service_fee_rate
    actual_received = contract_amount - service_fee
    
    # 每月还款按合同金额+月费率计算
    monthly_fee = contract_amount * monthly_fee_rate
    monthly_principal = contract_amount / months
    monthly_payment = monthly_principal + monthly_fee
    
    total_payment = monthly_payment * months
    total_cost = total_payment - actual_received  # 实际多付的钱
    
    # 用 IRR 计算真实年化
    cash_flows = [-actual_received] + [monthly_payment] * months
    irr = calculate_irr(cash_flows)
    
    # 复利年化 APR = (1+irr)^12 - 1
    apr = (1 + irr) ** 12 - 1 if irr else None
    nominal_apr = monthly_fee_rate * 12
    
    return {
        'contract_amount': round(contract_amount, 2),
        'service_fee': round(service_fee, 2),
        'actual_received': round(actual_received, 2),
        'monthly_payment': round(monthly_payment, 2),
        'total_payment': round(total_payment, 2),
        'total_cost': round(total_cost, 2),
        'nominal_apr': round(nominal_apr, 4),
        'real_apr': round(apr, 4) if apr else None,
    }


def calc_balloon_loan(principal: float, annual_rate: float, months: int,
                       balloon_ratio: float = 0.3) -> dict:
    """
    气球贷 - 前期小额还款，最后一期大额尾款

    正确模型：贷款本金 = 月供的年金现值 + 尾款的现值
        principal = monthly_payment × [1-(1+r)^-n]/r + balloon_amount × (1+r)^-n
    反解出月供。

    注意：不能把本金人为拆成"摊销部分"和"尾款部分"分别独立计算（即
    amortized = principal - balloon_amount 后单独对amortized做等额本息），
    那种算法等于把一笔贷款错误拆成两笔互不相关的贷款，会导致整体本金被多算，
    使反推出的真实APR远低于实际年化利率。

    Args:
        balloon_ratio: 尾款比例（默认30%，相对于总本金）
    """
    monthly_rate = annual_rate / 12
    balloon_amount = principal * balloon_ratio

    if monthly_rate > 0:
        pv_factor = (1 - (1 + monthly_rate) ** (-months)) / monthly_rate
        balloon_pv = balloon_amount * (1 + monthly_rate) ** (-months)
        monthly_payment = (principal - balloon_pv) / pv_factor
    else:
        # 零利率情况：本金减去尾款，平均分摊到各期
        monthly_payment = (principal - balloon_amount) / months

    total_payment = monthly_payment * months + balloon_amount
    total_interest = total_payment - principal

    # 用 IRR 验证/计算真实年化（应与传入的annual_rate基本一致，因为这里没有额外费用）
    cash_flows = [-principal]
    for i in range(months):
        if i == months - 1:
            cash_flows.append(monthly_payment + balloon_amount)
        else:
            cash_flows.append(monthly_payment)

    irr = calculate_irr(cash_flows)

    return {
        'monthly_payment': round(monthly_payment, 2),
        'balloon_amount': round(balloon_amount, 2),
        'total_payment': round(total_payment, 2),
        'total_interest': round(total_interest, 2),
        'apr': round((1 + irr) ** 12 - 1, 4) if irr else None,
    }


def calc_true_apr_from_payment(principal: float, monthly_payment: float,
                                months: int) -> dict:
    """
    已知贷款金额和每期还款额，反推真实 APR
    
    适用于：用户只知道"借X元，分Y期，每期还Z元"的情况
    
    Returns:
        {
            'principal': 贷款金额,
            'monthly_payment': 每期还款,
            'months': 期数,
            'total_payment': 总还款,
            'total_interest': 总利息,
            'irr_monthly': 月IRR,
            'apr': 真实年化利率
        }
    """
    total_payment = monthly_payment * months
    total_interest = total_payment - principal
    
    cash_flows = [-principal] + [monthly_payment] * months
    irr = calculate_irr(cash_flows)
    
    if irr is None:
        return {
            'error': 'IRR 计算失败',
            'principal': principal,
            'monthly_payment': monthly_payment,
            'total_payment': round(total_payment, 2),
            'total_interest': round(total_interest, 2),
        }
    
    # 复利年化 APR = (1+irr)^12 - 1
    apr = (1 + irr) ** 12 - 1 if irr else None
    
    return {
        'principal': principal,
        'monthly_payment': monthly_payment,
        'months': months,
        'total_payment': round(total_payment, 2),
        'total_interest': round(total_interest, 2),
        'irr_monthly': round(irr * 100, 4),
        'apr': round(apr, 2),
    }
