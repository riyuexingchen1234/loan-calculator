"""
贷款真相计算器 - 自然语言输入解析器
从用户的自然语言描述中提取贷款参数
"""

import re
from typing import Optional

# 中文数字映射（单字符）
CN_DIGIT_MAP = {
    '一': '1', '二': '2', '两': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '零': '0',
}

# 中文数字 → 阿拉伯数字（完整映射，按长度从大到小排序）
# 格式：(中文, 阿拉伯数字+万/千/百)
CN_FULL_NUM_MAP = [
    ('十二万', '12万'), ('十一万', '11万'),
    ('十万', '10万'), ('九万', '9万'), ('八万', '8万'),
    ('七万', '7万'), ('六万', '6万'), ('五万', '5万'),
    ('四万', '4万'), ('三万', '3万'), ('两万', '2万'),
    ('一万', '1万'), ('九千', '9千'), ('八百', '8百'),
    ('七百', '7百'), ('六百', '6百'), ('五百', '5百'),
    ('四百', '4百'), ('三百', '3百'), ('二百', '2百'), ('一百', '1百'),
]

# 中文数字 → 万几 的映射
CN_WAN_MAP = {
    '一万': 10000, '二万': 20000, '三万': 30000, '四万': 40000,
    '五万': 50000, '六万': 60000, '七万': 70000, '八万': 80000,
    '九万': 90000,
    '十万': 100000, '百万': 1000000, '千万': 10000000, '亿万': 100000000,
}

# 中文数字 → 阿拉伯数字（十几、二十几等组合数字，按长度从大到小排序，避免短串提前替换破坏长串）
CN_COMPOUND_NUM_MAP = [
    ('二十四', '24'), ('二十三', '23'), ('二十二', '22'), ('二十一', '21'),
    ('十九', '19'), ('十八', '18'), ('十七', '17'), ('十六', '16'),
    ('十五', '15'), ('十四', '14'), ('十三', '13'), ('十二', '12'), ('十一', '11'),
    ('三十六', '36'), ('二十', '20'), ('三十', '30'), ('十', '10'),
]

# 中文小数 → 阿拉伯小数（"零点X" "X点X"）
CN_DECIMAL_MAP = {
    '零点三': '0.3', '零点二': '0.2', '零点四': '0.4', '零点五': '0.5',
    '零点六': '0.6', '零点七': '0.7', '零点八': '0.8', '零点九': '0.9',
    '零点一': '0.1', '点三五': '.35', '点二八': '.28',
}


def _cn_digit_to_num(text: str) -> str:
    """将文本中的中文数字替换为阿拉伯数字"""
    result = text
    # 先处理小数（"零点三"类），避免被后面的单字替换破坏
    for cn, num in CN_DECIMAL_MAP.items():
        result = result.replace(cn, num)
    # 再处理中文完整数字（万/千/百，长度从大到小，避免短匹配覆盖长匹配）
    for cn, num in CN_FULL_NUM_MAP:
        result = result.replace(cn, num)
    # 再处理组合数字（十几、二十几），同样长度从大到小
    for cn, num in CN_COMPOUND_NUM_MAP:
        result = result.replace(cn, num)
    # 再处理"日息万X"组合中的中文数字
    for cn, num in CN_DIGIT_MAP.items():
        result = result.replace(f'万{cn}', f'万{num}')
    return result


def parse_loan_input(text: str) -> dict:
    """
    从自然语言输入中解析贷款参数
    
    Args:
        text: 用户输入的文本
        
    Returns:
        {
            'products': [...],
            'compare': bool
        }
    """
    # 中文数字预处理
    text = _cn_digit_to_num(text)
    text = text.strip()
    
    # 检测对比模式
    # 注意："和"/"与"单独使用过于宽泛——"和宣传的年化4.2%差多少"这种问句
    # 里的"和"只是在问"对比"这个动作本身，并不代表存在第二个贷款方案，
    # 因此"和"/"与"不能进入无条件触发列表，必须额外验证前后是否真的各有一套费率/期数信息。
    compare_keywords = ['对比', '比较', '比一下', '哪个划算', 'A方案', 'B方案',
                        'a方案', 'b方案', '还是']
    is_compare = any(kw in text for kw in compare_keywords)

    # "和"/"与"作为对比信号：要求同时满足
    # 1) 前后分别出现费率/期数等关键词（说明可能存在两套独立描述）
    # 2) "和/与"之后的部分不是"差多少/高多少/低多少"这种纯比较性问句——
    #    "和宣传的年化4.2%差多少"这种表达，本质是"一个真实值 vs 一个外部参照值"，
    #    只是在追问差距，并不是在描述第二笔独立的贷款，不应进入对比模式
    if not is_compare:
        rate_kw_pattern = r'(?:月费率|日息|年化|年利率|手续费|每期还|每月还)'
        compare_question_pattern = r'差多少|高多少|低多少|差几个百分点'
        for connector in ['和', '与']:
            if connector in text:
                idx = text.index(connector)
                before, after = text[:idx], text[idx + 1:]
                if (re.search(rate_kw_pattern, before)
                        and re.search(rate_kw_pattern, after)
                        and not re.search(compare_question_pattern, after)):
                    is_compare = True
                    break

    # 补充检测："A是.../B是..."这种独立标记模式（没有"方案"二字，也没有对比关键词）
    # 同时要求A和B都出现，避免单独一个"A"误判（如"A股"之类的误命中）
    if not is_compare:
        has_a_marker = bool(re.search(r'[Aa]\s*(?:是|：|:)', text))
        has_b_marker = bool(re.search(r'[Bb]\s*(?:是|：|:)', text))
        is_compare = has_a_marker and has_b_marker

    products = []
    
    if is_compare:
        products = _parse_compare_input(text)
    else:
        product = _parse_single_product(text)
        if product:
            products = [product]
    
    return {
        'products': products,
        'compare': is_compare and len(products) > 1,
    }


def _parse_single_product(text: str) -> Optional[dict]:
    """解析单个贷款产品"""
    product = {
        'name': '',
        'type': 'unknown',
        'principal': None,
        'months': None,
        'actual_days': None,  # 日息类产品的实际使用天数，可独立于months存在
        'payment_type': None,
        'monthly_payment': None,
        'monthly_fee_rate': None,
        'daily_rate': None,
        'annual_rate': None,
        'stated_apr': None,   # 用户转述的"宣传/销售口头告知"年化，仅用于报告对比展示，不参与计算
        'service_fee_rate': None,
        'extra_fees': [],
    }
    
    # 提取金额
    principal = _extract_amount(text)
    if principal:
        product['principal'] = principal
    
    # 提取期数
    months = _extract_months(text)
    if months:
        product['months'] = months

    # 提取实际使用天数（日息类产品可能只说天数，不说期数）
    actual_days = _extract_actual_days(text)
    if actual_days:
        product['actual_days'] = actual_days
    
    # 提取每期还款额
    payment = _extract_periodic_payment(text)
    if payment:
        product['monthly_payment'] = payment
    
    # 提取月费率/手续费率
    fee_rate = _extract_monthly_fee_rate(text)
    if fee_rate:
        product['monthly_fee_rate'] = fee_rate
        product['payment_type'] = 'credit_card_installment'
    
    # 提取日利率
    daily = _extract_daily_rate(text)
    if daily:
        product['daily_rate'] = daily
        product['payment_type'] = 'daily_interest'
    
    # 提取用户转述的"宣传/销售口头告知"年化（独立字段，不参与计算）
    stated = _extract_stated_apr(text)
    if stated:
        product['stated_apr'] = stated

    # 提取年利率（用于真实计费场景，如房贷/抵押贷的合同利率）。
    # 若已被识别为stated_apr（即带有"销售/宣传/客服说"等转述语境），
    # 则该数值只是用户被告知的宣传口径，不写入annual_rate，避免污染计算路径。
    if not stated:
        annual = _extract_annual_rate(text)
        if annual:
            product['annual_rate'] = annual
    
    # 提取服务费
    service_fee = _extract_service_fee(text)
    if service_fee is not None:
        product['service_fee_rate'] = service_fee
        if isinstance(service_fee, float) and service_fee >= 100:
            # 绝对金额（如"扣2000服务费"），标记为待转换
            product['service_fee_absolute'] = service_fee
        product['type'] = 'head_chopping'
    
    # 识别产品名称和类型
    product['name'], product['type'] = _identify_product_type(text)
    
    # 识别还款方式
    repayment_type = _identify_repayment_type(text)
    if repayment_type:
        product['payment_type'] = repayment_type
    
    return product if product['principal'] else None  # months允许为None，对比模式可继承


def _parse_compare_input(text: str) -> list:
    """解析对比模式的多个方案

    策略优先级：
    1. 若文本中出现"方案A/A方案"等显式标记，按标记在原文中的位置切片
       （而不是用re.split暴力分割，避免共享信息如本金被切散到错误片段）
    2. 否则尝试用"，"分隔的子句重新组合：若整体只提到一次本金/期数，
       则将其视为两个方案共享的信息，分别补充到每个子句中再解析
    3. 最后兜底：按"和"分隔，但只在分隔点两侧都已包含完整数字信息时才采用
    """
    # 策略1：显式"方案A/B"标记，按位置切片
    marker_pattern = r'(?:方案[AaBb]|[AaBb]方案)'
    markers = list(re.finditer(marker_pattern, text))

    products = []
    if len(markers) >= 2:
        boundaries = [m.start() for m in markers] + [len(text)]
        segments = []
        for i in range(len(markers)):
            segment = text[boundaries[i]:boundaries[i + 1]]
            # 去掉片段末尾的连接词残留（如"...分12期和"中的"和"）
            segment = re.sub(r'[和与]\s*$', '', segment).strip()
            label_match = re.search(r'([AaBb])', segment[:6])
            label = label_match.group(1).upper() if label_match else None
            segments.append((segment, label))

        # 先在所有切片中找出已提取到的本金/期数，作为共享信息备用
        # （某个切片可能没说本金，本金被另一切片"独占"了，需要互相回填）
        shared_principal = None
        shared_months = None
        for segment, _ in segments:
            amt = _extract_amount(segment)
            mon = _extract_months(segment)
            if amt and shared_principal is None:
                shared_principal = amt
            if mon and shared_months is None:
                shared_months = mon

        for segment, label in segments:
            product = _parse_single_product(segment)
            if product is None and shared_principal:
                # 该切片本身解析失败（很可能因为缺本金），补充共享本金后重试
                product = _parse_single_product(f"{segment}，借{shared_principal}元")
            if product:
                if product['principal'] is None and shared_principal:
                    product['principal'] = shared_principal
                if product['months'] is None and shared_months:
                    product['months'] = shared_months
                if label and not product['name']:
                    product['name'] = f'方案{label}'
                products.append(product)

    # 策略2：没有显式标记，尝试识别"共享本金/期数 + 多个费率描述"的模式
    # 例如"借5万，A是月费率0.3%分12期，B是日息万四"——本金只说了一次
    if len(products) < 2:
        shared_principal = _extract_amount(text)
        shared_months = _extract_months(text)

        # 按逗号切分成子句，每个含费率/利率关键词的子句视为一个方案描述
        rate_keywords = ['月费率', '日息', '年化', '年利率', '手续费', '每期还', '每月还']
        clauses = re.split(r'[，,]', text)

        # 二级切分：若某个逗号子句内部出现了2次以上费率关键词，
        # 说明两个方案的费率描述被"和/与"连在了同一个逗号子句里（没有逗号分隔），
        # 需要按"和/与"再切一次，否则会被当成一整条无法解析的子句
        refined_clauses = []
        for clause in clauses:
            kw_count = sum(clause.count(kw) for kw in rate_keywords)
            if kw_count >= 2 and re.search(r'和|与', clause):
                sub_parts = re.split(r'和|与', clause)
                refined_clauses.extend(sub_parts)
            else:
                refined_clauses.append(clause)

        candidate_clauses = [
            cl.strip() for cl in refined_clauses
            if any(kw in cl for kw in rate_keywords)
        ]

        if len(candidate_clauses) >= 2:
            products = []
            for idx, clause in enumerate(candidate_clauses):
                product = _parse_single_product(clause)
                if product is None:
                    # 子句本身可能没有本金信息，手动补充共享本金后重新解析
                    if shared_principal:
                        product = _parse_single_product(f"{clause}，借{shared_principal}元")
                if product:
                    if product['principal'] is None and shared_principal:
                        product['principal'] = shared_principal
                    if product['months'] is None and shared_months:
                        product['months'] = shared_months
                    if not product['name']:
                        product['name'] = f'方案{chr(65 + idx)}'  # A, B, C...
                    products.append(product)

    # 策略3兜底：按"和/与/还是"分隔，仅当两侧都能独立解析出本金时才采用
    # （若两侧解析出的本金相同，说明本金是共享信息被重复匹配，不视为分割错误）
    if len(products) < 2:
        parts = re.split(r'和|与|还是', text)
        candidate = []
        for part in parts:
            part = part.strip()
            if len(part) > 10:
                product = _parse_single_product(part)
                if product:
                    candidate.append(product)
        if len(candidate) >= 2:
            products = candidate

    # 对比模式补充：缺少金额或期数的方案从另一个方案继承
    if len(products) >= 2:
        for i in range(len(products)):
            other = products[1 - i] if len(products) == 2 else None
            if other:
                if products[i]['principal'] is None and other['principal'] is not None:
                    products[i]['principal'] = other['principal']
                if products[i]['months'] is None and other['months'] is not None:
                    products[i]['months'] = other['months']

    return products if len(products) >= 2 else []


def _extract_amount(text: str) -> Optional[float]:
    """提取贷款金额
    
    支持格式：
    - 借1万、1万元、借款5万 → 10000, 50000
    - 借10000元、10000元 → 10000
    - 贷款10万、10万元 → 100000
    - 纯数字+元：信用卡分期12000元 → 12000
    - 中文数字：十二万 → 120000
    """
    # 匹配：X万元 / X万（中文数字如"十二万"已在 _cn_digit_to_num 中转为"12万"）
    m = re.search(r'(\d+\.?\d*)\s*万', text)
    if m:
        return float(m.group(1)) * 10000
    
    # 匹配：数字元（前面有"借/贷款/分期/金额"等关键词）
    m = re.search(r'(?:借|借款|贷款|贷|分期|金额|信用卡)\s*(\d+\.?\d*)\s*元', text)
    if m:
        val = float(m.group(1))
        if val < 100:
            return val  # 可能是利率，但也可能是小额贷款
        return val
    
    # 匹配：借+数字（后面不是元/块/万，如"借5000到手"）
    m = re.search(r'(?:借|借款|贷款|贷)\s*(\d+\.?\d*)(?:\s|$|到|，|,|分)', text)
    if m:
        val = float(m.group(1))
        if val >= 100 and val < 1000000:
            return val
    
    # 匹配：纯数字+元/块（没有其他关键词）
    m = re.search(r'(\d+\.?\d*)\s*(?:元|块)', text)
    if m:
        val = float(m.group(1))
        if val >= 100 and val < 1000000:
            return val
    
    return None


def _extract_months(text: str) -> Optional[int]:
    """提取期数
    
    支持格式：
    - 分12期、12期、12个月
    - 3年 → 36期
    - 30年 → 360期
    - 半年 → 6期
    - 一年 → 12期
    - 两年 → 24期
    """
    # 期数
    m = re.search(r'分?(\d+)\s*期', text)
    if m:
        return int(m.group(1))
    
    # 月份
    m = re.search(r'(\d+)\s*个月', text)
    if m:
        return int(m.group(1))
    
    # 年数 → 期数
    m = re.search(r'(\d+)\s*年', text)
    if m:
        years = int(m.group(1))
        if years <= 30:  # 合理年限
            return years * 12
    
    # 中文年数
    cn_year_map = {'半': 0.5, '一': 1, '两': 2, '二': 2, '三': 3, '四': 4,
                   '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    for cn, yrs in cn_year_map.items():
        if f'{cn}年' in text:
            return int(yrs * 12)
    
    return None


def _extract_actual_days(text: str) -> Optional[int]:
    """提取实际使用天数（日息类产品常见表达，如"用了30天"）

    支持格式：
    - 用了30天、借了30天、用30天
    - 用了一周 → 7天、用了半个月 → 15天
    """
    m = re.search(r'(?:用|借|占用)?了?\s*(\d+)\s*天', text)
    if m:
        return int(m.group(1))

    if '一周' in text or '一星期' in text:
        return 7
    if '半个月' in text or '半月' in text:
        return 15

    return None


def _extract_periodic_payment(text: str) -> Optional[float]:
    """提取每期还款额"""
    patterns = [
        r'每期还?(\d+\.?\d*)',
        r'每期还款(\d+\.?\d*)',
        r'每月还?(\d+\.?\d*)',
        r'每月还款(\d+\.?\d*)',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return float(m.group(1))
    
    return None


def _extract_monthly_fee_rate(text: str) -> Optional[float]:
    """提取月费率
    
    支持格式：
    - 月费率0.3%、月费率0.28%
    - 月息X厘（1厘=0.1%）
    - 手续费率0.6%（等同于月费率）
    - 日息万X
    """
    # 月费率
    m = re.search(r'月费率(\d+\.?\d*)%', text)
    if m:
        return float(m.group(1)) / 100
    
    # 月息X厘
    m = re.search(r'月息(\d+\.?\d*)厘', text)
    if m:
        return float(m.group(1)) / 1000
    
    # 手续费率（等同于月费率）
    m = re.search(r'手续费?率\s*(\d+\.?\d*)%', text)
    if m:
        return float(m.group(1)) / 100
    
    return None


def _extract_daily_rate(text: str) -> Optional[float]:
    """提取日利率
    
    支持格式：
    - 日息万五 / 日息万5 / 日息万三五 → 0.0005
    - 日息万分之五 / 日息万分之5 → 0.0005
    - 日息0.05% → 0.0005
    - 万五息 → 0.0005
    """
    # 日息万X（阿拉伯数字）
    m = re.search(r'日息万(\d+)', text)
    if m:
        return float(m.group(1)) / 10000
    
    # 日息万分之X
    m = re.search(r'日息万分之?(\d+)', text)
    if m:
        return float(m.group(1)) / 10000
    
    # 日息X%
    m = re.search(r'日息(\d+\.?\d*)%', text)
    if m:
        return float(m.group(1)) / 100
    
    # 万X息（如万五息）
    m = re.search(r'万(\d+)\s*息', text)
    if m:
        return float(m.group(1)) / 10000
    
    return None


def _extract_annual_rate(text: str) -> Optional[float]:
    """提取年利率（用于真实计费场景，如房贷/抵押贷的合同利率）"""
    patterns = [
        r'(?:年化?|年利率?)\s*(?:为|是|才|只有)?\s*(\d+\.?\d*)%',
        # 兜底：直接说"利率X%"，没有"年"字前缀（房贷/车贷场景常见，
        # 默认按年利率理解，因为月费率/日息有各自独立的关键词，不会与此冲突）
        r'利率\s*(?:为|是|才|只有)?\s*(\d+\.?\d*)%',
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return float(m.group(1)) / 100

    return None


def _extract_stated_apr(text: str) -> Optional[float]:
    """提取用户转述的"宣传/对比"年化利率，仅用于报告中的对比展示，不参与计算

    典型场景：
    - "销售说年利率才5.6%"（用户被告知的宣传值，但计费方式实际是其他口径）
    - "宣传年化4.2%"
    - "广告写的年化XX%"

    与 _extract_annual_rate 的区别：
    该函数捕获的是"被宣传/被告知"的值，调用方应将其放入 stated_apr 字段单独展示，
    不应让它进入实际计算路径（实际计算应以 monthly_fee_rate/daily_rate/monthly_payment 为准）。
    """
    patterns = [
        r'(?:销售|客服|对方|他们|中介|宣传|广告|说|写的?)\s*(?:年化?|年利率?)\s*(?:为|是|才|只有)?\s*(\d+\.?\d*)%',
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return float(m.group(1)) / 100

    return None


def _extract_service_fee(text: str) -> Optional[float]:
    """提取服务费
    
    支持格式：
    - 扣200服务费 / 扣2000元服务费 → 2000（绝对金额）
    - 服务费2% / 服务费5% → 0.02（比例）
    - 借5000到手4000 → 1000（合同金额-到手金额）
    """
    # "借X到手Y" → 服务费 = X - Y（兼容"到手只有/仅/才Y"这种带修饰语的表达）
    m = re.search(r'借\s*(\d+\.?\d*)\s*(?:元|块|万)?\s*到手\s*(?:只有|仅|才)?\s*(\d+\.?\d*)', text)
    if m:
        contract = float(m.group(1))
        actual = float(m.group(2))
        if contract > actual:
            return contract - actual  # 返回绝对金额
    
    # 服务费比例
    m = re.search(r'服?务?费\s*(\d+\.?\d*)%', text)
    if m:
        return float(m.group(1)) / 100
    
    # 扣X元/块服务费
    m = re.search(r'扣\s*(\d+\.?\d*)\s*(?:元|块)?\s*服?务?费', text)
    if m:
        return float(m.group(1))
    
    # 服务费X元（前置）
    m = re.search(r'服?务?费\s*(\d+\.?\d*)\s*(?:元|块)', text)
    if m:
        return float(m.group(1))
    
    return None


def _identify_product_type(text: str) -> tuple:
    """识别产品名称和贷款类型"""
    name_map = {
        '借呗': ('借呗', 'daily_interest'),
        '微粒贷': ('微粒贷', 'daily_interest'),
        '京东金条': ('京东金条', 'daily_interest'),
        '花呗': ('花呗', 'credit_card_installment'),
        '信用卡': ('信用卡', 'credit_card_installment'),
        '信用卡分期': ('信用卡', 'credit_card_installment'),
        '抵押': ('抵押贷款', 'mortgage'),
        '抵押贷': ('抵押贷款', 'mortgage'),
        '经营贷': ('经营贷', 'interest_first_principal_last'),
        '网贷': ('网贷', 'unknown'),
        '信用贷': ('信用贷', 'credit_loan'),
        '消费贷': ('消费贷', 'credit_loan'),
        '消费分期': ('消费分期', 'credit_card_installment'),
        '房贷': ('房贷', 'mortgage'),
        '公积金': ('公积金贷款', 'mortgage'),
        '银行': ('银行贷款', 'credit_loan'),
        '气球': ('气球贷', 'balloon'),
    }
    
    for keyword, (name, ptype) in name_map.items():
        if keyword in text:
            return name, ptype
    
    return '', 'unknown'


def _identify_repayment_type(text: str) -> Optional[str]:
    """识别还款方式"""
    type_map = {
        '等额本息': 'equal_principal_interest',
        '等额本金': 'equal_principal',
        '先息后本': 'interest_first_principal_last',
        '按期付息到期还本': 'interest_first_principal_last',
        '随借随还': 'daily_interest',
        '气球': 'balloon',
    }
    
    for keyword, ptype in type_map.items():
        if keyword in text:
            return ptype
    
    return None
