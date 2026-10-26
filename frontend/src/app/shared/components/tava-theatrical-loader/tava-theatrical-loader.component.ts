import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnDestroy,
  ViewChild,
} from '@angular/core';

@Component({
  selector: 'tava-theatrical-loader',
  standalone: true,
  templateUrl: './tava-theatrical-loader.component.html',
  styleUrl: './tava-theatrical-loader.component.scss',
})
export class TavaTheatricalLoaderComponent implements AfterViewInit, OnDestroy {
  @Input() title = 'Preparando el escenario';

  /** Mientras es true, el telón avanza. Si la carga se detiene, queda en false y la escena no se mueve. */
  @Input()
  set moving(value: boolean) {
    this.shouldMove = value;
    if (!this.ready) return;
    if (value) this.start();
    else this.stop();
  }

  @ViewChild('escena') private escena?: ElementRef<HTMLElement>;
  @ViewChild('logo') private logo?: ElementRef<HTMLElement>;
  @ViewChild('logoPleno') private logoPleno?: ElementRef<HTMLElement>;
  @ViewChild('comedia') private comedia?: ElementRef<HTMLElement>;
  @ViewChild('tragedia') private tragedia?: ElementRef<HTMLElement>;
  @ViewChild('luzA') private luzA?: ElementRef<HTMLElement>;
  @ViewChild('luzB') private luzB?: ElementRef<HTMLElement>;
  @ViewChild('halo') private halo?: ElementRef<HTMLElement>;
  @ViewChild('proscenio') private proscenio?: ElementRef<HTMLElement>;

  readonly oroId = `gOro-${Math.random().toString(36).slice(2, 8)}`;
  readonly burdeosId = `gBurdeos-${Math.random().toString(36).slice(2, 8)}`;

  percent = 0;
  stageLine = 'Sala en penumbra';

  private readonly host: HTMLElement;
  private readonly reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  private readonly logoRatio = 0.5822222222222222;
  private readonly maskRatio = 280 / 260;
  private readonly face = 168 / 280;
  private shouldMove = true;
  private ready = false;
  private progress = 0;
  private elapsed = 0;
  private runningSince = 0;
  private raf = 0;
  private resizeObserver?: ResizeObserver;
  private measures = { H: 220, logoW: 128, finalX: 180, inicioX: 420 };

  constructor(host: ElementRef<HTMLElement>) {
    this.host = host.nativeElement;
  }

  ngAfterViewInit(): void {
    this.ready = true;
    this.measure();
    this.paint(this.reduced ? 100 : 0);
    this.resizeObserver = new ResizeObserver(() => {
      this.measure();
      this.paint(this.progress);
    });
    this.resizeObserver.observe(this.host);
    if (this.shouldMove) this.start();
  }

  ngOnDestroy(): void {
    this.stop();
    this.resizeObserver?.disconnect();
  }

  private start(): void {
    if (this.reduced) {
      this.progress = 100;
      this.paint(100);
      return;
    }
    if (this.raf) return;
    this.runningSince = performance.now();
    const step = (now: number) => {
      if (!this.shouldMove) {
        this.raf = 0;
        return;
      }
      const total = this.elapsed + (now - this.runningSince);
      const target = Math.min(92, (total / 14000) * 92);
      if (target - this.progress > 0.04) {
        this.progress = target;
        this.paint(this.progress);
      }
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  private stop(): void {
    if (this.runningSince) {
      this.elapsed += performance.now() - this.runningSince;
      this.runningSince = 0;
    }
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private measure(): void {
    const width = this.host.clientWidth || this.host.parentElement?.clientWidth || 360;
    const heightCap = Math.min(window.innerHeight * 0.46, 420);
    const span = this.logoRatio + 2 * this.face * this.maskRatio * 0.86 + 0.16;
    const H = Math.max(150, Math.min(heightCap, (width * 0.92) / span));
    const logoW = H * this.logoRatio;
    const maskH = H * 0.86;
    const maskW = maskH * this.maskRatio;
    const faceW = maskW * this.face;
    let finalX = logoW / 2 + faceW / 2 + H * 0.08;
    const limit = width / 2 - faceW / 2 - 8;
    if (finalX > limit) finalX = Math.max(limit, logoW / 2);
    const style = this.host.style;
    style.setProperty('--alto-escena', `${H * 1.16}px`);
    style.setProperty('--logo-h', `${H}px`);
    style.setProperty('--logo-w', `${logoW}px`);
    style.setProperty('--masc-h', `${maskH}px`);
    style.setProperty('--masc-w', `${maskW}px`);
    style.setProperty('--luz-w', `${faceW * 1.7}px`);
    style.setProperty('--halo-w', `${H * 1.5}px`);
    style.setProperty('--proscenio-w', `${finalX * 2 + faceW}px`);
    this.measures = { H, logoW, finalX, inicioX: width / 2 + maskW * 0.6 };
  }

  private paint(value: number): void {
    const p = Math.min(100, Math.max(0, value));
    const { H, logoW, finalX, inicioX } = this.measures;
    const t = p / 100;
    const e = 1 - (1 - t) ** 3;
    const breath = Math.sin(t * Math.PI * 4) * 0.022;
    const turn = -3 * (1 - e) + 1.4 * Math.sin(t * Math.PI * 3);
    const rise = H * 0.035 * (1 - e);
    if (this.logo) {
      this.logo.nativeElement.style.transform = `translateY(${rise.toFixed(2)}px) rotate(${turn.toFixed(3)}deg) scale(${(0.9 + 0.1 * e + breath).toFixed(4)})`;
    }

    const m = this.inOut(Math.min(1, t / 0.82));
    const arc = Math.sin(Math.PI * m);
    const xC = -inicioX + (inicioX + finalX) * m;
    const bow = Math.sin(Math.PI * this.clamp((t - 0.8) / 0.2));
    const open = 1 - (1 - this.clamp((t - 0.8) / 0.2)) ** 3;
    const depth = 1 + 0.14 * arc;
    const yC = -H * 0.1 * arc + H * 0.05 * bow;
    const yT = H * 0.1 * arc + H * 0.05 * bow;
    const rotC = 9 * arc - 12 * bow + 6 * open;
    const rotT = -9 * arc + 12 * bow - 6 * open;
    if (this.comedia) {
      this.comedia.nativeElement.style.transform = `translate(${xC.toFixed(2)}px, ${yC.toFixed(2)}px) rotate(${rotC.toFixed(3)}deg) scale(${depth.toFixed(4)})`;
    }
    if (this.tragedia) {
      this.tragedia.nativeElement.style.transform = `translate(${(-xC).toFixed(2)}px, ${yT.toFixed(2)}px) rotate(${rotT.toFixed(3)}deg) scale(${depth.toFixed(4)})`;
    }

    let left = 50;
    let right = 50;
    if (xC > -xC) {
      left = this.clamp((-xC + logoW / 2) / logoW) * 100;
      right = this.clamp((logoW / 2 - xC) / logoW) * 100;
    }
    if (this.logoPleno) {
      this.logoPleno.nativeElement.style.clipPath = `inset(-4% ${right.toFixed(2)}% -4% ${left.toFixed(2)}%)`;
    }

    const glow = (0.15 + 0.85 * arc) * (1 - open * 0.85) * this.clamp(t * 6);
    if (this.luzA) {
      this.luzA.nativeElement.style.transform = `translateX(${xC.toFixed(2)}px)`;
      this.luzA.nativeElement.style.opacity = glow.toFixed(3);
    }
    if (this.luzB) {
      this.luzB.nativeElement.style.transform = `translateX(${(-xC).toFixed(2)}px)`;
      this.luzB.nativeElement.style.opacity = glow.toFixed(3);
    }
    if (this.halo) {
      this.halo.nativeElement.style.opacity = (0.25 + 0.75 * e).toFixed(3);
      this.halo.nativeElement.style.transform = `scale(${(0.8 + 0.2 * e).toFixed(4)})`;
    }
    if (this.proscenio) {
      this.proscenio.nativeElement.style.transform = `scaleX(${e.toFixed(4)})`;
      this.proscenio.nativeElement.style.opacity = (0.3 + 0.7 * e).toFixed(3);
    }

    const rounded = Math.round(p);
    this.percent = rounded;
    const lines: [number, string][] = [
      [0, 'Sala en penumbra'],
      [1, 'Se apagan las luces de la sala'],
      [25, 'Entran las máscaras'],
      [55, 'Se abre el telón'],
      [85, 'Reverencia'],
      [100, 'Comienza la función'],
    ];
    let line = lines[0][1];
    for (const [from, text] of lines) if (rounded >= from) line = text;
    this.stageLine = line;
    this.escena?.nativeElement.setAttribute('aria-valuenow', String(rounded));
  }

  private clamp(value: number): number {
    return Math.min(1, Math.max(0, value));
  }

  private inOut(t: number): number {
    return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
  }
}
