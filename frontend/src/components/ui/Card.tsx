import { useId, type ReactNode } from 'react'

interface Props {
  title?: string
  headingLevel?: 2 | 3
  className?: string
  children: ReactNode
}

/** Glass surface (see `.card` in tokens.css): translucent fill, blur, hairline border. */
export function Card({ title, headingLevel = 2, className, children }: Props) {
  const id = useId()
  const Heading = `h${headingLevel}` as 'h2' | 'h3'
  return (
    <section className={`card${className ? ` ${className}` : ''}`} aria-labelledby={title ? id : undefined}>
      {title && (
        <Heading id={id} className="card__title">
          {title}
        </Heading>
      )}
      {children}
    </section>
  )
}
