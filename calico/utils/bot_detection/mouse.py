import math, random, asyncio

def bezier_curve(p0, p1, p2, p3, t):
    """Cubic Bézier curve function"""
    return (
        (1 - t)**3 * p0
        + 3 * (1 - t)**2 * t * p1
        + 3 * (1 - t) * t**2 * p2
        + t**3 * p3
    )

async def human_mouse_move(page, start, end, duration=1.0, steps=50):
    """
    Move mouse like a human: Bézier curve + jitter + easing
    - start: (x0, y0)
    - end:   (x1, y1)
    """
    x0, y0 = start
    x3, y3 = end

    # Random control points (add noise to simulate natural curve)
    x1, y1 = x0 + (x3 - x0) * 0.3 + random.randint(-50, 50), y0 + random.randint(-100, 100)
    x2, y2 = x0 + (x3 - x0) * 0.7 + random.randint(-50, 50), y3 + random.randint(-100, 100)

    for step in range(steps + 1):
        # Ease-in-out timing
        t = step / steps
        t = (math.sin((t - 0.5) * math.pi) + 1) / 2  

        x = bezier_curve(x0, x1, x2, x3, t)
        y = bezier_curve(y0, y1, y2, y3, t)

        # Small jitter
        x += random.uniform(-1, 1)
        y += random.uniform(-1, 1)

        await page.mouse.move(x, y, steps=1)
        await asyncio.sleep(duration / steps)


#await human_mouse_move(page, (100, 200), (600, 400), duration=1.5, steps=80)