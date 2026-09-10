"""Small, editable CPU projects; training data is explicitly synthetic."""
import json

GENERAL = {
    'src/app.py': '''import json

def summarize(values):
    if not values:
        raise ValueError("At least one value required")
    return {"count": len(values), "total": sum(values), "average": sum(values) / len(values)}

if __name__ == "__main__":
    print(json.dumps(summarize([12, 18, 24]), ensure_ascii=False))
''',
    'tests/test_app.py': '''import unittest
from src.app import summarize

class AppTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(summarize([2, 4]), {"count": 2, "total": 6, "average": 3})
    def test_empty(self):
        with self.assertRaises(ValueError):
            summarize([])
''',
}
AI = {
    'src/train.py': '''"""Train and evaluate a linear model on synthetic data using gradient descent."""
import csv
import json
import os
from pathlib import Path

def train(rows, epochs=400, learning_rate=0.05):
    weight, bias = 0.0, 0.0
    losses = []
    for epoch in range(epochs):
        errors = [(weight * x + bias - y, x) for x, y in rows]
        weight -= learning_rate * 2 * sum(e * x for e, x in errors) / len(rows)
        bias -= learning_rate * 2 * sum(e for e, _ in errors) / len(rows)
        loss = sum((weight * x + bias - y) ** 2 for x, y in rows) / len(rows)
        losses.append(loss)
    return {"weight": weight, "bias": bias}, losses

def evaluate(model, rows):
    return sum((model["weight"] * x + model["bias"] - y) ** 2 for x, y in rows) / len(rows)

if __name__ == "__main__":
    with open("data/synthetic.csv", newline="") as f:
        rows = [(float(r["x"]), float(r["y"])) for r in csv.DictReader(f)]
    training, held_out = rows[::2], rows[1::2]
    model, losses = train(training)
    metrics = {"dataset": "synthetic-linear-v1", "trainingRows": len(training),
               "evaluationRows": len(held_out), "epochs": len(losses),
               "initialLoss": losses[0], "finalLoss": losses[-1],
               "evaluationMSE": evaluate(model, held_out), "device": "cpu"}
    output = Path(os.environ.get("SV_OUTPUT_DIR", "outputs"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "model.json").write_text(json.dumps(model, indent=2))
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (output / "loss.csv").write_text("epoch,loss\\n" + "".join(f"{i+1},{loss}\\n" for i, loss in enumerate(losses)))
    print(json.dumps(metrics, indent=2))
''',
    'tests/test_train.py': '''import unittest
from src.train import train, evaluate

class TrainingTest(unittest.TestCase):
    def test_generalizes(self):
        model, losses = train([(-1, -1), (0, 2), (1, 5)])
        self.assertLess(losses[-1], losses[0])
        self.assertLess(evaluate(model, [(0.5, 3.5), (-0.5, 0.5)]), 1e-8)
''',
    'data/synthetic.csv': 'x,y\n' + ''.join(f'{i/50},{3*i/50+2}\n' for i in range(-50, 51)),
}


def template(kind):
    if kind not in ('python', 'ai'):
        raise ValueError('Unknown project template')
    files = dict(AI if kind == 'ai' else GENERAL)
    files['.gitignore'] = '.venv/\n__pycache__/\n*.pyc\n.env\n.env.*\noutputs/\n.studio/\n'
    files['README.md'] = ('# SaintVision 개발 Workspace\n\n'
        + ('합성 데이터로 실제 CPU 모델 학습과 별도 평가를 수행하는 시작 프로젝트입니다. GPU 학습·사용자 데이터 학습 결과가 아닙니다.\n' if kind == 'ai' else '일반 Python 개발·테스트 시작 프로젝트입니다.\n')
        + '\nStudio에서 Workspace를 선택하고 도구를 여세요. 변경 파일은 실행 시 스냅샷으로 고정됩니다.\n'
          '작업 결과는 Studio의 실행 기록에서 확인·다운로드합니다. 로컬 개발 환경은 .venv를 사용하세요.\n'
          '여러 Agent는 서로 다른 Workspace에서 작업하고 Git diff로 통합하세요.\n')
    instructions = ('# 개발 Agent 공통 지침\n\n이 프로젝트의 README.md를 먼저 읽는다.\n'
        'Codex: 실행·무결성·아키텍처. Claude: 서비스·데이터 처리·테스트. Gemini/Antigravity: UI·시각화.\n'
        '작업당 작성자 하나. 다른 Agent 검토를 했다고 꾸미지 않는다.\n'
        '등록된 Studio 작업으로 테스트·학습하고 실제 출력·종료 코드·파일 해시를 보고한다.\n'
        '외부 파일·인증정보를 작업 입력에 넣지 않는다. outputs는 결과이며 정본 코드가 아니다.\n'
        '일반 편집·로컬 검증은 진행한다. 데이터 삭제·배포·계정 변경은 범위와 승인을 확인한다.\n')
    files['AGENTS.md'] = instructions
    files['CLAUDE.md'] = 'Read AGENTS.md and README.md before working.\n'
    files['GEMINI.md'] = 'Read AGENTS.md and README.md before working.\n'
    tasks = {'test': {'label': '단위 테스트', 'argv': ['python', '-m', 'unittest', 'discover', '-s', 'tests', '-v']}}
    tasks['train' if kind == 'ai' else 'run'] = {
        'label': 'CPU 학습·평가' if kind == 'ai' else '프로그램 실행',
        'argv': ['python', 'src/train.py' if kind == 'ai' else 'src/app.py']}
    return files, tasks
