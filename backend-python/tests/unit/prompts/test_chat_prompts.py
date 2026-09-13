"""
聊天系统提示词：引用记号必须与链路里**真实出现**的记号一致。

背景（2026-09-13）：提示词原本教模型写 `[p.12]`，而 `ContextBuilder.render()` 写进上下文块的
是 `[来源 N]` —— 两个记号对不上。L2 实测 40 条可评测答案里**只有 14 条带引用**（35%）：
模型被要求用一套记号、上下文里是另一套，于是照自己的来或干脆不写。

这条测试把"记号一致"锁住，避免以后又漂移。
"""

from app.prompts.chat_prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_PROMPT_TPL


def test_system_prompt_teaches_the_marker_the_pipeline_actually_writes():
    """教给模型的记号，就是 render() 真实写进上下文的那个（`[来源 N]`）。"""
    assert "[来源 1]" in CHAT_SYSTEM_PROMPT


def test_system_prompt_no_longer_teaches_a_conflicting_marker():
    """旧的 `[p.12]` 示例必须消失 —— 它和真实记号冲突，是引用率低的根因。"""
    assert "[p.12]" not in CHAT_SYSTEM_PROMPT


def test_system_prompt_forbids_inventing_markers_and_answers():
    """不许编造记号、不许编造信息 —— 这两条是可溯源与拒答的前提。"""
    assert "Never invent" in CHAT_SYSTEM_PROMPT
    assert "Do not fabricate" in CHAT_SYSTEM_PROMPT


def test_user_prompt_template_keeps_context_and_question_slots():
    """模板仍能用真实上下文与问题渲染（别在改提示词时把占位符弄丢）。"""
    substituted = CHAT_USER_PROMPT_TPL.substitute(
        context="[来源 1]\nChapitre 1", question="这门课讲什么？"
    )

    assert "[来源 1]" in substituted
    assert "这门课讲什么？" in substituted
