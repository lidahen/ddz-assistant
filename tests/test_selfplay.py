"""规则 AI 自对弈压力测试: 大量随机对局，验证引擎闭环不出错。"""
import sys
sys.path.insert(0, r'D:\load\zcode\ddz-assistant')

from ddz.core.game import Game
from ddz.core.rule_ai import RuleAI

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
wins = {'p0': 0, 'p1': 0, 'p2': 0}
errors = 0
for i in range(N):
    try:
        g = Game(seed=i)
        ais = {p: RuleAI() for p in ('p0', 'p1', 'p2')}
        w = g.run(ais)
        wins[w] += 1
    except Exception as e:
        errors += 1
        print(f'game {i} ERROR: {type(e).__name__}: {e}')
        if errors > 5:
            break

print(f'{N} games, errors={errors}, landlord(p0) winrate={wins["p0"]/N:.2%}')
sys.exit(1 if errors else 0)
