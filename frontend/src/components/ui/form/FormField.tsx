import React from 'react'
import { useFormContext } from 'react-hook-form'
import { Label } from '@components/3rdparty/ui/label'
import { cn } from '@lib/utils'

interface FormFieldProps {
  name: string
  label?: string
  children: React.ReactElement<any>
}

export function FormField({ name, label, children }: FormFieldProps) {
  const {
    register,
    formState: { errors }
  } = useFormContext()

  const error = errors[name]?.message as string | undefined

  return (
    <div className="space-y-2">
      {label && <Label htmlFor={name}>{label}</Label>}

      {React.cloneElement(children, {
        ...register(name),
        id: name,
        error: !!error,
        className: cn(children?.props?.className, error && 'border-destructive')
      })}

      {error && (
        <p className="text-sm text-destructive animate-fade-in">{error}</p>
      )}
    </div>
  )
}
