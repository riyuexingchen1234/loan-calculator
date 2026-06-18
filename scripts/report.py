"""
贷款真相计算器 - 报告生成器
生成简洁结果 + 详细说明的中文报告
"""

import os
import sys
from typing import Optional

# 沙箱兼容：确保 scripts 目录在 Python path 中
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from calculator import (
    calc_equal_principal_interest,
    calc_equal_principal,
    calc_interest_first_principal_last,
    calc_credit_card_installment,
    calc_daily_interest_loan,
    calc_head_chopping_loan,
    calc_balloon_loan,
    calc_true_apr_from_payment,
    calculate_irr,
)


def generate_report(products: list, compare_mode: bool = False) -> str:
    """
    生成贷款分析报告
    
    Args:
        products: 解析后的产品信息列表
        compare_mode: 是否为对比模式
        
    Returns:
        格式化报告文本
    """
    if compare_mode and len(products) >= 2:
        return _generate_compare_report(products)
    elif len(products) == 1:
        return _generate_single_report(products[0])
    else:
        return "⚠️ 未能解析贷款信息。请提供以下信息：\n" \
               "- 贷款金额（如：1万元、10000元）\n" \
               "- 期数（如：12期、3年）\n" \
               "- 还款信息（如：每期还880元、月费率0.3%、日息万五）"


def _generate_single_report(product: dict) -> str:
    """生成单方案报告"""
    principal = product['principal']
    months = product['months']
    name = product.get('name', '该贷款')
    
    # 根据贷款类型计算
    payment_type = product.get('payment_type') or product.get('type', 'unknown')
    
    # 砍头息优先判断：有service_fee_rate就意味着是砍头息，不论payment_type
    if product.get('service_fee_rate') is not None and isinstance(product.get('service_fee_rate'), (int, float)):
        if product['service_fee_rate'] < 1:
            svc_rate = product['service_fee_rate']
        else:
            svc_rate = product['service_fee_rate'] / principal

        if product.get('monthly_payment'):
            # 用户已明确给出真实每月还款额——必须用这个真实值反推APR，
            # 不能套用虚构的默认费率去重新"计算"一个月供，那样会丢弃用户提供的真实信息。
            #
            # 关键点：IRR现金流的初始放款应该是"实际到手金额"，不是"合同金额"——
            # 用户真实占用的资金是到手的那部分，借贷关系的现金流起点应以此为准，
            # 这样算出的APR才反映用户真实承担的资金成本。
            service_fee_amount = principal * svc_rate if svc_rate < 1 else product['service_fee_rate']
            actual_received = principal - service_fee_amount
            real_monthly_payment = product['monthly_payment']

            cash_flows = [-actual_received] + [real_monthly_payment] * months
            irr = calculate_irr(cash_flows)
            real_apr = (1 + irr) ** 12 - 1 if irr else None

            total_payment = real_monthly_payment * months
            total_cost = total_payment - actual_received

            # 宣传年化：按"合同金额计息但用户只当它是普通分期"理解的名义值，
            # 即假设利息=每月手续费部分×12/合同金额这种粗略口径，仅供对比展示
            nominal_apr = (total_cost / actual_received / (months / 12)) if actual_received > 0 and months > 0 else None

            result = {
                'contract_amount': principal,
                'service_fee': round(service_fee_amount, 2),
                'actual_received': round(actual_received, 2),
                'monthly_payment': round(real_monthly_payment, 2),
                'total_payment': round(total_payment, 2),
                'total_cost': round(total_cost, 2),
                'nominal_apr': round(nominal_apr, 4) if nominal_apr else None,
                'real_apr': round(real_apr, 4) if real_apr else None,
            }
        else:
            # 用户没说每月还款额，只能用假定费率走理论模型估算
            fee_rate = product.get('monthly_fee_rate') or 0.003
            result = calc_head_chopping_loan(
                principal, svc_rate, fee_rate, months
            )
        return _format_head_chopping_report(name, product, result)
    
    elif payment_type == 'credit_card_installment' and product.get('monthly_fee_rate'):
        result = calc_credit_card_installment(
            principal, product['monthly_fee_rate'], months
        )
        if 'error' in result:
            return f"⚠️ 计算失败：{result['error']}"
        return _format_credit_card_report(name, product, result)
    
    elif payment_type == 'daily_interest' and product.get('daily_rate'):
        result = calc_daily_interest_loan(
            principal, product['daily_rate'], months,
            actual_days=product.get('actual_days')
        )
        if 'error' in result:
            return f"⚠️ {result['error']}。请补充：用了多少天，或预计用多少个月。"
        return _format_daily_report(name, product, result)
    
    elif product.get('monthly_payment') and product.get('principal'):
        # 已知每期还款额，反推 APR
        result = calc_true_apr_from_payment(
            principal, product['monthly_payment'], months
        )
        if 'error' in result:
            return f"⚠️ 计算失败：{result['error']}"
        return _format_reverse_report(name, product, result)
    
    elif product.get('annual_rate'):
        # 有明确年利率
        annual_rate = product['annual_rate']
        if payment_type == 'equal_principal':
            result = calc_equal_principal(principal, annual_rate, months)
            return _format_equal_principal_report(name, product, result)
        elif payment_type == 'interest_first_principal_last':
            result = calc_interest_first_principal_last(principal, annual_rate, months)
            return _format_interest_first_report(name, product, result)
        else:
            result = calc_equal_principal_interest(principal, annual_rate, months)
            return _format_equal_principal_interest_report(name, product, result)
    
    else:
        return "⚠️ 信息不足，无法计算。请提供：\n" \
               "- 贷款金额\n" \
               "- 期数\n" \
               "- 利率/费率/每期还款额中的至少一项"


def _format_credit_card_report(name: str, product: dict, result: dict) -> str:
    """格式化信用卡分期/月费率报告"""
    apr = result['apr']
    nominal = result['nominal_rate']
    multiplier = result['fee_multiplier']
    
    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 真实年化利率分析")
    lines.append(f"{'═'*50}")
    lines.append("")
    
    # 简洁结果
    lines.append(f"  💰 贷款金额：{product['principal']:,.0f}元")
    lines.append(f"  📅 分期期数：{product['months']}期")
    lines.append(f"  📋 每月还款：{result['monthly_payment']:,.2f}元")
    lines.append(f"  📋 每月手续费：{result['monthly_fee']:,.2f}元")
    lines.append(f"  💸 总手续费：{result['total_fee']:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append("")
    
    # 核心结果 — 真实 APR
    lines.append(f"{'─'*50}")
    lines.append(f"  🔍 真实年化利率（APR）")
    lines.append(f"{'─'*50}")
    lines.append(f"  宣传年化：{nominal*100:.2f}%  （月费率 × 12）")
    lines.append(f"  真实年化：{apr*100:.2f}%  （IRR 精确计算）")
    lines.append(f"  ⚠️  真实利率是宣传值的 {multiplier:.1f} 倍！")
    lines.append("")
    
    # 风险提示
    lines.append(f"{'─'*50}")
    lines.append(f"  ⚠️  套路解析")
    lines.append(f"{'─'*50}")
    lines.append(f"  手续费按全额收取，不按剩余本金递减。")
    lines.append(f"  你每个月都在为已经还掉的本金继续付手续费！")
    lines.append(f"  实际占用本金逐月减少，但手续费不变，")
    lines.append(f"  所以真实利率远高于宣传值。")
    lines.append("")
    
    # 还款计划
    lines.append(f"{'─'*50}")
    lines.append(f"  📋 还款计划表（前6期 + 最后1期）")
    lines.append(f"{'─'*50}")
    lines.append(f"  {'期数':>4}  {'还款':>10}  {'本金':>10}  {'手续费':>10}  {'剩余':>10}")
    schedule = result['schedule']
    for i in range(min(6, len(schedule))):
        s = schedule[i]
        lines.append(f"  {s['period']:>4}  {s['payment']:>10,.2f}  {s['principal']:>10,.2f}  "
                     f"{s['fee']:>10,.2f}  {s['remaining']:>10,.2f}")
    if len(schedule) > 7:
        lines.append(f"  ...")
    s = schedule[-1]
    lines.append(f"  {s['period']:>4}  {s['payment']:>10,.2f}  {s['principal']:>10,.2f}  "
                 f"{s['fee']:>10,.2f}  {s['remaining']:>10,.2f}")
    lines.append("")
    
    return '\n'.join(lines)


def _format_daily_report(name: str, product: dict, result: dict) -> str:
    """格式化日息贷款报告"""
    apr = result['apr']
    daily_display = result['daily_rate'] * 10000
    months = product.get('months')
    actual_days = result.get('actual_days')

    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 真实年化利率分析")
    lines.append(f"{'═'*50}")
    lines.append("")

    lines.append(f"  💰 贷款金额：{product['principal']:,.0f}元")
    if months:
        lines.append(f"  📅 预计使用：{months}个月（约{actual_days}天）")
    else:
        lines.append(f"  📅 实际使用：{actual_days}天")
    lines.append(f"  📋 日利率：万{daily_display:.0f}（{result['daily_rate']*100:.4f}%）")
    lines.append(f"  💸 总利息：{result['total_interest']:,.2f}元")
    if result.get('monthly_interest') is not None:
        lines.append(f"  💸 月均利息：{result['monthly_interest']:,.2f}元")
    lines.append("")

    lines.append(f"{'─'*50}")
    lines.append(f"  🔍 真实年化利率（APR）")
    lines.append(f"{'─'*50}")
    lines.append(f"  日利率：万{daily_display:.0f}")
    lines.append(f"  真实年化：{apr*100:.2f}%  （日利率 × 365）")
    lines.append("")
    
    # 风险提示
    lines.append(f"{'─'*50}")
    lines.append(f"  ⚠️  套路解析")
    lines.append(f"{'─'*50}")
    if apr > 0.24:
        lines.append(f"  ⛔ 年化利率超过24%！属于高利贷范畴！")
        lines.append(f"  法律保护的上限是年化24%，超过部分不受法律保护。")
    elif apr > 0.18:
        lines.append(f"  ⚠️  年化利率超过18%，非常高！")
    else:
        lines.append(f"  日息看起来很低，但换算成年化其实不低。")
    lines.append(f"  日息万五 = 年化18.25%，日息万三 = 年化10.95%")
    lines.append("")
    
    return '\n'.join(lines)


def _format_head_chopping_report(name: str, product: dict, result: dict) -> str:
    """格式化砍头息报告"""
    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 真实年化利率分析")
    lines.append(f"{'═'*50}")
    lines.append("")
    
    lines.append(f"  💰 合同金额：{result['contract_amount']:,.0f}元")
    lines.append(f"  💸 服务费（砍头）：{result['service_fee']:,.2f}元")
    lines.append(f"  💵 实际到手：{result['actual_received']:,.0f}元")
    lines.append(f"  📋 每月还款：{result['monthly_payment']:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append(f"  💸 实际多付：{result['total_cost']:,.2f}元")
    lines.append("")
    
    lines.append(f"{'─'*50}")
    lines.append(f"  🔍 真实年化利率（APR）")
    lines.append(f"{'─'*50}")
    lines.append(f"  宣传年化：{result['nominal_apr']*100:.2f}%")
    if result['real_apr']:
        lines.append(f"  真实年化：{result['real_apr']*100:.2f}%  （IRR 精确计算）")
    lines.append("")
    
    lines.append(f"{'─'*50}")
    lines.append(f"  ⚠️  套路解析")
    lines.append(f"{'─'*50}")
    lines.append(f"  1. 服务费前置扣除（砍头息）：你借{result['contract_amount']:,.0f}元，")
    lines.append(f"     实际只拿到{result['actual_received']:,.0f}元，少了{result['service_fee']:,.2f}元")
    lines.append(f"  2. 但利息/手续费按{result['contract_amount']:,.0f}元全额计算")
    lines.append(f"  3. 等于你用更少的钱，承担了更高的利率")
    lines.append(f"  4. 这是最恶劣的贷款套路之一！")
    lines.append("")
    
    return '\n'.join(lines)


def _format_reverse_report(name: str, product: dict, result: dict) -> str:
    """格式化反推 APR 报告（已知每期还款额）"""
    apr = result['apr']
    total_interest = result['total_interest']
    principal = result['principal']
    months = result['months']
    monthly_payment = result['monthly_payment']
    stated_apr = product.get('stated_apr')

    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 真实年化利率分析")
    lines.append(f"{'═'*50}")
    lines.append("")

    lines.append(f"  💰 贷款金额：{principal:,.0f}元")
    lines.append(f"  📅 分期期数：{months}期")
    lines.append(f"  📋 每期还款：{monthly_payment:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append(f"  💸 总利息：{total_interest:,.2f}元")
    lines.append("")

    lines.append(f"{'─'*50}")
    lines.append(f"  🔍 真实年化利率（APR）")
    lines.append(f"{'─'*50}")
    if stated_apr is not None:
        # 用户明确提到了销售/宣传告知的年化，直接做对比，不再用脱离输入的估算公式
        diff = apr - stated_apr
        multiple = apr / stated_apr if stated_apr > 0 else None
        lines.append(f"  对方告知的年化：{stated_apr*100:.2f}%")
        lines.append(f"  真实年化：{apr*100:.2f}%  （IRR 精确计算）")
        lines.append("")
        if multiple is not None:
            lines.append(f"  ⚠️  真实年化是对方告知值的 {multiple:.2f} 倍，"
                          f"相差 {diff*100:.2f} 个百分点。")
        else:
            lines.append(f"  ⚠️  真实年化比对方告知值高 {diff*100:.2f} 个百分点。")
    else:
        # 用户没提到任何宣传值，仅给出粗略估算供参考，并明确标注是估算
        estimated_nominal = (total_interest / principal / (months / 12)) * 0.5 if months > 0 and principal > 0 else 0
        lines.append(f"  粗略估算的名义年化：~{estimated_nominal*100:.2f}%（仅供参考，未基于任何宣传信息）")
        lines.append(f"  真实年化：{apr*100:.2f}%  （IRR 精确计算）")
    lines.append("")
    
    # 风险提示
    lines.append(f"{'─'*50}")
    lines.append(f"  ⚠️  风险评估")
    lines.append(f"{'─'*50}")
    if apr > 0.36:
        lines.append(f"  ⛔ 年化利率超过36%！属于超高利贷！")
        lines.append(f"  超过36%的部分不受法律保护，可向法院主张返还。")
    elif apr > 0.24:
        lines.append(f"  ⛔ 年化利率超过24%！超过法律保护上限！")
        lines.append(f"  超过24%的部分不受法律保护。")
    elif apr > 0.18:
        lines.append(f"  ⚠️  年化利率超过18%，非常高！")
    elif apr > 0.10:
        lines.append(f"  ⚠️  年化利率超过10%，偏高。")
    else:
        lines.append(f"  ✅ 年化利率在合理范围内。")
    lines.append("")
    
    return '\n'.join(lines)


def _format_equal_principal_interest_report(name: str, product: dict, result: dict) -> str:
    """格式化等额本息报告"""
    apr = product.get('annual_rate', 0) * 100
    
    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 等额本息还款分析")
    lines.append(f"{'═'*50}")
    lines.append("")
    
    lines.append(f"  💰 贷款金额：{product['principal']:,.0f}元")
    lines.append(f"  📅 分期期数：{product['months']}期")
    lines.append(f"  📋 年利率：{apr:.2f}%")
    lines.append(f"  📋 每月还款：{result['monthly_payment']:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append(f"  💸 总利息：{result['total_interest']:,.2f}元")
    lines.append("")
    
    lines.append(f"{'─'*50}")
    lines.append(f"  📋 还款计划表（前6期 + 最后1期）")
    lines.append(f"{'─'*50}")
    lines.append(f"  {'期数':>4}  {'还款':>10}  {'本金':>10}  {'利息':>10}  {'剩余':>10}")
    schedule = result['schedule']
    for i in range(min(6, len(schedule))):
        s = schedule[i]
        lines.append(f"  {s['period']:>4}  {s['payment']:>10,.2f}  {s['principal']:>10,.2f}  "
                     f"{s['interest']:>10,.2f}  {s['remaining']:>10,.2f}")
    if len(schedule) > 7:
        lines.append(f"  ...")
    s = schedule[-1]
    lines.append(f"  {s['period']:>4}  {s['payment']:>10,.2f}  {s['principal']:>10,.2f}  "
                 f"{s['interest']:>10,.2f}  {s['remaining']:>10,.2f}")
    lines.append("")
    
    return '\n'.join(lines)


def _format_equal_principal_report(name: str, product: dict, result: dict) -> str:
    """格式化等额本金报告"""
    apr = product.get('annual_rate', 0) * 100
    
    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 等额本金还款分析")
    lines.append(f"{'═'*50}")
    lines.append("")
    
    lines.append(f"  💰 贷款金额：{product['principal']:,.0f}元")
    lines.append(f"  📅 分期期数：{product['months']}期")
    lines.append(f"  📋 年利率：{apr:.2f}%")
    lines.append(f"  📋 首月还款：{result['first_month']:,.2f}元")
    lines.append(f"  📋 末月还款：{result['last_month']:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append(f"  💸 总利息：{result['total_interest']:,.2f}元")
    lines.append("")
    
    return '\n'.join(lines)


def _format_interest_first_report(name: str, product: dict, result: dict) -> str:
    """格式化先息后本报告"""
    apr = product.get('annual_rate', 0) * 100
    
    lines = []
    lines.append(f"{'═'*50}")
    lines.append(f"  📊 {name} — 先息后本还款分析")
    lines.append(f"{'═'*50}")
    lines.append("")
    
    lines.append(f"  💰 贷款金额：{product['principal']:,.0f}元")
    lines.append(f"  📅 分期期数：{product['months']}期")
    lines.append(f"  📋 年利率：{apr:.2f}%")
    lines.append(f"  📋 每月利息：{result['monthly_interest']:,.2f}元")
    lines.append(f"  💸 总利息：{result['total_interest']:,.2f}元")
    lines.append(f"  💸 总还款：{result['total_payment']:,.2f}元")
    lines.append(f"  ⏰ 到期需还本金：{result['final_principal']:,.0f}元")
    lines.append("")
    
    lines.append(f"{'─'*50}")
    lines.append(f"  ⚠️  风险提示")
    lines.append(f"{'─'*50}")
    lines.append(f"  先息后本表面利率很低，但到期需一次性偿还全部本金。")
    lines.append(f"  如果到期无法一次性拿出本金，可能需要续贷，")
    lines.append(f"  续贷会产生新的手续费，实际成本会更高。")
    lines.append("")
    
    return '\n'.join(lines)


def _generate_compare_report(products: list) -> str:
    """生成多方案对比报告"""
    lines = []
    lines.append(f"{'═'*60}")
    lines.append(f"  📊 贷款方案对比分析")
    lines.append(f"{'═'*60}")
    lines.append("")
    
    results = []
    for i, product in enumerate(products, 1):
        name = product.get('name', f'方案{i}')
        apr = _get_apr_for_product(product)
        if apr is not None:
            results.append((name, apr, product))
    
    if not results:
        return "⚠️ 无法计算所有方案的 APR，请检查输入信息。"
    
    # 按 APR 排序
    results.sort(key=lambda x: x[1])
    
    # 对比表格
    lines.append(f"  {'方案':>4}  {'名称':<12}  {'真实年化':>10}  {'评价':<10}")
    lines.append(f"  {'─'*50}")
    
    for rank, (name, apr, _) in enumerate(results, 1):
        if apr < 0.06:
            eval_str = "✅ 很低"
        elif apr < 0.10:
            eval_str = "✅ 较低"
        elif apr < 0.18:
            eval_str = "⚠️ 偏高"
        elif apr < 0.24:
            eval_str = "⛔ 很高"
        else:
            eval_str = "⛔ 超高！"
        lines.append(f"  #{rank:>2}  {name:<12}  {apr*100:>8.2f}%  {eval_str:<10}")
    
    lines.append("")
    
    # 推荐最优
    best_name, best_apr, _ = results[0]
    lines.append(f"  🏆 推荐方案：{best_name}")
    lines.append(f"  真实年化利率：{best_apr*100:.2f}%")
    lines.append("")
    
    # 详细对比
    if len(results) >= 2:
        lines.append(f"{'─'*60}")
        lines.append(f"  💡 成本差异分析")
        lines.append(f"{'─'*60}")
        worst_name, worst_apr, worst_product = results[-1]
        lines.append(f"  最优方案 {best_name} 比 最差方案 {worst_name} 的")
        lines.append(f"  年化利率低 {(worst_apr - best_apr)*100:.2f} 个百分点")
        lines.append(f"  相差 {(worst_apr / best_apr):.1f} 倍！")
        lines.append("")
    
    # 各方案详情
    for name, apr, product in results:
        lines.append(f"{'─'*60}")
        lines.append(f"  📋 {name} 详情")
        lines.append(f"{'─'*60}")
        lines.append(f"  金额：{product['principal']:,.0f}元 | 期数：{product['months']}期")
        lines.append(f"  真实年化：{apr*100:.2f}%")
        
        # 附加信息
        if product.get('monthly_payment'):
            lines.append(f"  每期还款：{product['monthly_payment']:,.2f}元")
        if product.get('monthly_fee_rate'):
            lines.append(f"  宣传月费率：{product['monthly_fee_rate']*100:.2f}%")
            lines.append(f"  宣传年化：{product['monthly_fee_rate']*12*100:.2f}%")
            lines.append(f"  真实是宣传的 {(apr / (product['monthly_fee_rate']*12)):.1f} 倍")
        if product.get('daily_rate'):
            lines.append(f"  日利率：万{product['daily_rate']*10000:.0f}")
        lines.append("")
    
    return '\n'.join(lines)


def _get_apr_for_product(product: dict) -> Optional[float]:
    """获取产品的 APR（返回小数形式，如 0.0658 表示 6.58%）"""
    payment_type = product.get('payment_type') or product.get('type', 'unknown')
    principal = product['principal']
    months = product['months']
    
    try:
        # 砍头息优先判断
        if product.get('service_fee_rate') is not None:
            svc_rate = product['service_fee_rate']
            if svc_rate >= 100:
                svc_rate = svc_rate / principal
            fee_rate = product.get('monthly_fee_rate', 0.003)
            result = calc_head_chopping_loan(principal, svc_rate, fee_rate, months)
            apr = result.get('real_apr')
            return apr if apr else None
        
        elif payment_type == 'credit_card_installment' and product.get('monthly_fee_rate'):
            result = calc_credit_card_installment(principal, product['monthly_fee_rate'], months)
            apr = result.get('apr')
            return apr if apr else None
        
        elif payment_type == 'daily_interest' and product.get('daily_rate'):
            result = calc_daily_interest_loan(principal, product['daily_rate'], months)
            apr = result.get('apr')
            return apr if apr else None
        
        elif product.get('monthly_payment') and principal:
            result = calc_true_apr_from_payment(principal, product['monthly_payment'], months)
            apr = result.get('apr')
            return apr if apr else None
        
        elif product.get('annual_rate'):
            return product['annual_rate']
    except Exception:
        return None
    
    return None
