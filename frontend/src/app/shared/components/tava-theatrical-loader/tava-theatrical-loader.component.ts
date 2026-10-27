import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  ElementRef,
  Input,
  NgZone,
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
  @ViewChild('comedia') private comedia?: ElementRef<HTMLElement>;
  @ViewChild('tragedia') private tragedia?: ElementRef<HTMLElement>;
  @ViewChild('halo') private halo?: ElementRef<HTMLElement>;
  @ViewChild('proscenio') private proscenio?: ElementRef<HTMLElement>;

  readonly oroId = `gOro-${Math.random().toString(36).slice(2, 8)}`;
  readonly burdeosId = `gBurdeos-${Math.random().toString(36).slice(2, 8)}`;

  percent = 0;
  stageLine = 'Sala en penumbra';

  private readonly host: HTMLElement;
  private readonly reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  private shouldMove = true;
  private ready = false;
  private progress = 0;
  private elapsed = 0;
  private runningSince = 0;
  private raf = 0;
  private lastPaintAt = 0;
  private lastLine = '';
  private resizeObserver?: ResizeObserver;
  private measures = { size: 148, finalX: 118, inicioX: 210 };

  constructor(
    host: ElementRef<HTMLElement>,
    private readonly zone: NgZone,
    private readonly changes: ChangeDetectorRef,
  ) {
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
    if (this.shouldMove) this.zone.runOutsideAngular(() => this.start());
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
    this.host.classList.add('is-moving');
    const step = (now: number) => {
      if (!this.shouldMove) {
        this.raf = 0;
        return;
      }
      const total = this.elapsed + (now - this.runningSince);
      const target = Math.min(92, (total / 4500) * 92);
      if (target - this.progress >= 0.35 && now - this.lastPaintAt >= 40) {
        this.progress = target;
        this.lastPaintAt = now;
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
    this.host.classList.remove('is-moving');
  }

  private measure(): void {
    const width = this.host.clientWidth || this.host.parentElement?.clientWidth || 360;
    const size = Math.max(112, Math.min(168, width * 0.22, window.innerHeight * 0.2));
    const mask = size * 0.92;
    const gap = size * 0.08;
    let finalX = size / 2 + mask * 0.28 + gap;
    const limit = width / 2 - mask * 0.42;
    if (finalX > limit) finalX = Math.max(limit, size * 0.55);
    const inicioX = Math.min(width * 0.38, Math.max(finalX + size * 0.35, width / 2 - mask * 0.55));
    const style = this.host.style;
    style.setProperty('--alto-escena', `${size * 1.35}px`);
    style.setProperty('--logo-size', `${size}px`);
    style.setProperty('--masc-size', `${mask}px`);
    style.setProperty('--halo-size', `${size * 1.55}px`);
    style.setProperty('--proscenio-w', `${finalX * 2 + mask * 0.55}px`);
    this.measures = { size, finalX, inicioX };
  }

  private paint(value: number): void {
    const p = Math.min(100, Math.max(0, value));
    const { size, finalX, inicioX } = this.measures;
    const t = p / 100;
    const e = 1 - (1 - t) ** 3;
    const m = this.inOut(Math.min(1, t / 0.7));
    const x = -inicioX + (inicioX + finalX) * m;
    const lift = Math.sin(Math.PI * m) * size * 0.04;
    const rot = (1 - m) * 8;

    if (this.logo) {
      const scale = 0.92 + 0.08 * e;
      this.logo.nativeElement.style.transform = `translateY(${((1 - e) * size * 0.04).toFixed(2)}px) scale(${scale.toFixed(3)})`;
    }
    if (this.comedia) {
      this.comedia.nativeElement.style.transform = `translate(${x.toFixed(1)}px, ${(-lift).toFixed(1)}px) rotate(${(-rot).toFixed(2)}deg)`;
    }
    if (this.tragedia) {
      this.tragedia.nativeElement.style.transform = `translate(${(-x).toFixed(1)}px, ${lift.toFixed(1)}px) rotate(${rot.toFixed(2)}deg)`;
    }
    if (this.halo) {
      this.halo.nativeElement.style.opacity = (0.2 + 0.55 * e).toFixed(2);
    }
    if (this.proscenio) {
      this.proscenio.nativeElement.style.transform = `scaleX(${(0.35 + 0.65 * e).toFixed(3)})`;
      this.proscenio.nativeElement.style.opacity = (0.35 + 0.55 * e).toFixed(2);
    }

    const rounded = Math.round(p);
    const lines: [number, string][] = [
      [0, 'Sala en penumbra'],
      [8, 'Se apagan las luces de la sala'],
      [20, 'Entran las máscaras'],
      [45, 'Se abre el telón'],
      [72, 'Reverencia'],
      [90, 'Comienza la función'],
    ];
    let line = lines[0][1];
    for (const [from, text] of lines) if (rounded >= from) line = text;
    if (line !== this.lastLine) {
      this.lastLine = line;
      this.stageLine = line;
      this.percent = rounded;
      this.zone.run(() => this.changes.markForCheck());
    } else {
      this.percent = rounded;
    }
    this.escena?.nativeElement.setAttribute('aria-valuenow', String(rounded));
  }

  private inOut(t: number): number {
    return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
  }
}
