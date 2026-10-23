import {
  AfterViewInit,
  Component,
  effect,
  ElementRef,
  EventEmitter,
  inject,
  OnDestroy,
  Output,
  ViewChild,
} from '@angular/core';
import { environment } from '../../../../environments/environment';
import { SiteSettingsService } from '../../../core/services/site-settings.service';

declare global {
  interface Window {
    hcaptcha?: {
      render: (
        container: HTMLElement | string,
        options: {
          sitekey: string;
          size?: string;
          theme?: string;
          callback: (token: string) => void;
          'expired-callback'?: () => void;
          'error-callback'?: () => void;
        }
      ) => number;
      reset: (widgetId?: number) => void;
      remove: (widgetId?: number) => void;
    };
  }
}

@Component({
  selector: 'tava-captcha',
  standalone: true,
  templateUrl: './tava-captcha.component.html',
  styleUrl: './tava-captcha.component.scss',
})
export class TavaCaptchaComponent implements AfterViewInit, OnDestroy {
  private readonly site = inject(SiteSettingsService);
  @ViewChild('hcaptchaHost') hcaptchaHost?: ElementRef<HTMLDivElement>;
  @Output() tokenChange = new EventEmitter<string>();

  enabled = false;
  readonly useHcaptcha = Boolean(environment.hcaptchaSiteKey);
  devConfirmed = false;
  private widgetId: number | null = null;
  private scriptLoaded = false;

  constructor() {
    this.site.loadAppearance();
    effect(() => {
      const app = this.site.appearance();
      if (!app) return;
      this.enabled = !!app.captcha_enabled;
      if (!this.enabled) this.tokenChange.emit('captcha-disabled');
    });
  }

  ngAfterViewInit(): void {
    if (!this.enabled) this.tokenChange.emit('captcha-disabled');
    if (this.useHcaptcha) {
      void this.initHcaptcha();
    }
  }

  ngOnDestroy(): void {
    if (this.widgetId != null && window.hcaptcha) {
      try {
        window.hcaptcha.remove(this.widgetId);
      } catch {
        /* ignore */
      }
    }
  }

  onDevConfirm(checked: boolean): void {
    this.devConfirmed = checked;
    this.tokenChange.emit(checked ? 'dev-captcha' : '');
  }

  reset(): void {
    if (this.useHcaptcha && this.widgetId != null && window.hcaptcha) {
      window.hcaptcha.reset(this.widgetId);
      this.tokenChange.emit('');
      return;
    }
    this.devConfirmed = false;
    this.tokenChange.emit('');
  }

  private async initHcaptcha(): Promise<void> {
    await this.loadScript();
    const host = this.hcaptchaHost?.nativeElement;
    if (!host || !window.hcaptcha || !environment.hcaptchaSiteKey) return;
    this.widgetId = window.hcaptcha.render(host, {
      sitekey: environment.hcaptchaSiteKey,
      size: 'normal',
      theme: 'dark',
      callback: (token) => this.tokenChange.emit(token),
      'expired-callback': () => this.tokenChange.emit(''),
      'error-callback': () => this.tokenChange.emit(''),
    });
  }

  private loadScript(): Promise<void> {
    if (this.scriptLoaded || window.hcaptcha) {
      this.scriptLoaded = true;
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-tava-hcaptcha]');
      if (existing) {
        existing.addEventListener('load', () => {
          this.scriptLoaded = true;
          resolve();
        });
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://js.hcaptcha.com/1/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.dataset['tavaHcaptcha'] = '1';
      script.onload = () => {
        this.scriptLoaded = true;
        resolve();
      };
      script.onerror = () => reject(new Error('No se pudo cargar hCaptcha'));
      document.body.appendChild(script);
    });
  }
}
