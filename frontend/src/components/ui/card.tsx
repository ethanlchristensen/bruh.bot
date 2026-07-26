import * as React from 'react';
import { cn } from '@/lib/utils';

type CardVariant = 'hero' | 'standard' | 'inset';

interface CardContextValue {
  variant: CardVariant;
}

const CardContext = React.createContext<CardContextValue>({ variant: 'standard' });

const cardVariants: Record<CardVariant, { root: string; header: string; content: string; footer: string; gap: string }> = {
  hero: {
    root: 'rounded-2xl border-2 border-primary/10 shadow-lg shadow-primary/5 py-8',
    header: 'px-8',
    content: 'px-8',
    footer: 'px-8',
    gap: 'gap-8',
  },
  standard: {
    root: 'rounded-xl border border-border/50 shadow-sm py-8',
    header: 'px-8',
    content: 'px-8',
    footer: 'px-8',
    gap: 'gap-8',
  },
  inset: {
    root: 'rounded-lg bg-muted/30 py-5',
    header: 'px-6',
    content: 'px-6',
    footer: 'px-6',
    gap: 'gap-5',
  },
};

function useCardContext() {
  return React.useContext(CardContext);
}

interface CardProps extends React.ComponentProps<'div'> {
  variant?: CardVariant;
}

function Card({ className, variant = 'standard', ...props }: CardProps) {
  const styles = cardVariants[variant];

  return (
    <CardContext.Provider value={{ variant }}>
      <div
        data-slot="card"
        data-variant={variant}
        className={cn(
          'bg-card text-card-foreground flex flex-col shadow-sm',
          styles.root,
          styles.gap,
          className,
        )}
        {...props}
      />
    </CardContext.Provider>
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<'div'>) {
  const { variant } = useCardContext();
  const styles = cardVariants[variant];

  return (
    <div
      data-slot="card-header"
      className={cn(
        '@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-2 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6',
        styles.header,
        className,
      )}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<'div'>) {
  const { variant } = useCardContext();

  return (
    <div
      data-slot="card-title"
      className={cn(
        'leading-none font-semibold',
        variant === 'hero' && 'text-xl',
        className,
      )}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-description"
      className={cn('text-muted-foreground text-sm', className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        'col-start-2 row-span-2 row-start-1 self-start justify-self-end',
        className,
      )}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<'div'>) {
  const { variant } = useCardContext();
  const styles = cardVariants[variant];

  return (
    <div
      data-slot="card-content"
      className={cn(styles.content, className)}
      {...props}
    />
  );
}

function CardFooter({ className, ...props }: React.ComponentProps<'div'>) {
  const { variant } = useCardContext();
  const styles = cardVariants[variant];

  return (
    <div
      data-slot="card-footer"
      className={cn('flex items-center [.border-t]:pt-6', styles.footer, className)}
      {...props}
    />
  );
}

interface CardIconProps {
  children: React.ReactNode;
  variant?: CardVariant;
  className?: string;
}

function CardIcon({ children, variant: variantProp, className }: CardIconProps) {
  const ctx = useCardContext();
  const variant = variantProp ?? ctx.variant;
  const isHero = variant === 'hero';

  return (
    <div
      data-slot="card-icon"
      className={cn(
        'shrink-0 rounded-xl flex items-center justify-center',
        isHero
          ? 'p-3 bg-primary/10 text-primary'
          : 'p-2.5 bg-muted text-muted-foreground',
        className,
      )}
    >
      {React.isValidElement(children)
        ? React.cloneElement(children as React.ReactElement<{ className?: string }>, {
            className: cn(
              (children as React.ReactElement<{ className?: string }>).props.className,
              isHero ? 'h-6 w-6' : 'h-5 w-5',
            ),
          })
        : children}
    </div>
  );
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
  CardIcon,
  type CardVariant,
};