import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { TavaContactFabComponent } from '../../shared/components/tava-contact-fab/tava-contact-fab.component';
import { TavaPopupComponent } from '../../shared/components/tava-popup/tava-popup.component';
import { TavaChatbotComponent } from '../../shared/components/tava-chatbot/tava-chatbot.component';
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
    TavaChatbotComponent,
  ],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly site = inject(SiteSettingsService);
  private readonly router = inject(Router);
  private readonly idle = inject(SessionIdleService);
  private readonly warmup = inject(ApiWarmupService);
  private readonly keepAlive = inject(ApiKeepAliveService);
  private readonly eventsPrefetch = inject(EventsPrefetchService);
  private navSub?: Subscription;

  menuOpen = false;
  readonly pendingReviewCount = signal(0);

  ngOnInit(): void {
    void this.warmup.wake();
    this.site.loadAppearance();
    this.eventsPrefetch.prefetch();
    this.keepAlive.start();
    this.idle.start();
    this.loadPendingReviewCount();
    this.navSub = this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => {
        this.closeMenu();
        this.loadPendingReviewCount();
      });
  }

  private loadPendingReviewCount(): void {
    if (!this.auth.isPlatformAdmin()) {
      this.pendingReviewCount.set(0);
      return;
    }
    this.api.get<{ count: number }>('/events/admin/review-pending-count').subscribe({
      next: (res) => this.pendingReviewCount.set(res.count ?? 0),
      error: () => this.pendingReviewCount.set(0),
    });
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
