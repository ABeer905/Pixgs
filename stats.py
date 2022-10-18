from datetime import datetime

'''
Measure usage per day
'''
class Stats:
    canvases = 0
    edit = 0
    move = 0
    color = 0
    draw = 0
    help = 0
    cur = 0
    last_day = 0

    def out(log):
        t = datetime.now()
        if t.hour == 0 and t.day != Stats.last_day:
            Stats.last_day = t.day
            log.info('Daily requests: canvases {} edits {} moves {} colors {} draws {} helps {} cursor_tog {}'.format(
                Stats.canvases,
                Stats.edit,
                Stats.move,
                Stats.color,
                Stats.draw,
                Stats.help,
                Stats.cur
            ))
            Stats.canvases = 0
            Stats.edit = 0
            Stats.move = 0
            Stats.color = 0
            Stats.draw = 0
            Stats.help = 0
            Stats.cur = 0





