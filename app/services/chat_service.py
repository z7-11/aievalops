INJECTION_KEYWORDS = (
    "忽略之前",
    "系统提示词",
    "system prompt",
    "开发者指令",
)


def generate_answer(question: str) -> str:
    """根据用户问题生成模拟客服答案。"""

    normalized_question = str(question or "").strip()

    if not normalized_question:
        return "请输入需要咨询的问题。"

    lower_question = normalized_question.lower()

    contains_injection = any(keyword.lower() in lower_question for keyword in INJECTION_KEYWORDS)

    if contains_injection:
        return "抱歉，我不能提供系统提示词或内部配置信息。"

    if "退款" in normalized_question:
       return "商品签收后7天内可以申请退款，请在订单详情页提交退款申请。"
       # return "商品签收后3天内可以申请退款，请联系客服电话处理。"

    if "工作时间" in normalized_question or "营业时间" in normalized_question:
        return "人工客服工作时间为每天09:00至18:00。"

    if "运费" in normalized_question or "包邮" in normalized_question:
        return "订单满99元包邮，未满99元收取10元运费。"

    return "暂时没有找到相关答案，请联系人工客服处理。"
