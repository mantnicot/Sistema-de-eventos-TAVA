import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { TavaContactFabComponent } from '../../shared/components/tava-contact-fab/tava-contact-fab.component';
import { TavaPopupComponent } from '../../shared/components/tava-popup/tava-popup.component';
import { SessionIdleService } from '../../core/services/session-idle.service';
import { ApiWarmupService } from '../../core/services/api-warmup.service';
import { ApiKeepAliveService } from '../../core/services/api-keep-alive.service';
import { EventsPrefetchService } from '../../core/services/events-prefetch.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    TavaPopupComponent,
    TavaContactFabComponent,
  ],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  private readonly site = inject(SiteSettingsService);
  private readonly router = inject(Router);
  private readonly idle = inject(SessionIdleService);
  private readonly warmup = inject(ApiWarmupService);
  private readonly keepAlive = inject(ApiKeepAliveService);
  private readonly eventsPrefetch = inject(EventsPrefetchService);
  private navSub?: Subscription;

  menuOpen = false;

  ngOnInit(): void {
    void this.warmup.wake();
    this.site.loadAppearance();
    this.eventsPrefetch.prefetch();
    this.keepAlive.start();
    this.idle.start();
    this.navSub = this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => this.closeMenu());
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
    this.keepAlive.stop();
  }

  closeMenu(): void {
    this.menuOpen = false;
  }

  logout(): void {
    this.closeMenu();
    this.auth.logout();
  }
}
