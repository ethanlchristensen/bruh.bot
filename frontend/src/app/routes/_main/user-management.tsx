import { useEffect, useMemo, useState } from 'react'; // Added useMemo
import { createFileRoute } from '@tanstack/react-router';
import { Check, Loader2, Plus, RotateCcw, Trash2 } from 'lucide-react'; // Added RotateCcw
import { z } from 'zod';

import { toast } from 'sonner';
import { useConfig, useUpdateConfig } from '@/hooks/use-config';
import { useConfigChanges } from '@/contexts/config-changes-context';
import { Spinner } from '@/components/ui/spinner';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export const Route = createFileRoute('/_main/user-management')({
  component: UserManagementComponent,
});

const AdminIdSchema = z
  .string()
  .length(18, 'Admin ID must be exactly 18 characters')
  .regex(/^\d+$/, 'Admin ID must contain only numbers');

function UserManagementComponent() {
  const { data, isLoading } = useConfig();
  const { addConfigChange } = useConfigChanges();
  const updateConfig = useUpdateConfig();

  const [admins, setAdmins] = useState<Array<string>>([]);
  const [addAdminId, setAddAdminId] = useState<string>('');
  const [errors, setErrors] = useState<Array<string> | null>(null);

  // Initialize admins from data
  useEffect(() => {
    if (!data?.config?.adminIds) return;
    setAdmins(data.config.adminIds);
  }, [data]);

  // 1. Logic to clear the "Checkmark" success state after 3 seconds
  useEffect(() => {
    if (updateConfig.isSuccess) {
      const timer = setTimeout(() => {
        updateConfig.reset();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [updateConfig.isSuccess, updateConfig.reset]);

  // 2. Logic to detect if there are unsaved changes
  const hasChanges = useMemo(() => {
    const original = data?.config?.adminIds || [];
    if (original.length !== admins.length) return true;
    return (
      JSON.stringify([...original].sort()) !==
      JSON.stringify([...admins].sort())
    );
  }, [data, admins]);

  async function handleSaveChanges() {
    setErrors(null);
    await updateConfig.mutateAsync(
      { adminIds: admins },
      {
        onSuccess: () => {
          toast.success('Admins have been updated successfully');
        },
        onError: (err) => {
          setErrors([err.message]);
          toast.error('Failed to update Admins.');
        },
      },
    );
  }

  // 3. Logic to undo changes
  function handleUndo() {
    const original = data?.config?.adminIds || [];
    setAdmins(original);
    addConfigChange({ adminIds: original });
    setErrors(null);
    toast.info('Changes discarded');
  }

  function handleAddAdmin() {
    setErrors(null);
    const result = AdminIdSchema.safeParse(addAdminId);

    if (!result.success) {
      setErrors(result.error.issues.map((issue) => issue.message));
      return;
    }

    if (admins.includes(addAdminId)) {
      setErrors(['This ID is already an admin']);
      return;
    }

    const newAdmins = [...admins, addAdminId];
    setAdmins(newAdmins);
    addConfigChange({ adminIds: newAdmins });
    setAddAdminId('');
  }

  function handleRemoveAdmin(idToRemove: string) {
    const newAdmins = admins.filter((id) => id !== idToRemove);
    setAdmins(newAdmins);
    addConfigChange({ adminIds: newAdmins });
  }

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-start justify-start p-10">
        <div className="flex gap-2 items-center">
          <Spinner />
          Loading configuration data
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Card id="admin-list-card" className="max-w-2xl">
        <CardHeader>
          <CardTitle>
            <div className="flex items-center justify-between gap-2">
              Admin List
              <div className="flex gap-2">
                {/* Undo Button */}
                {hasChanges && (
                  <Button variant="outline" onClick={handleUndo} size="sm">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Undo
                  </Button>
                )}

                <Button
                  onClick={handleSaveChanges}
                  disabled={updateConfig.isPending || !hasChanges}
                  variant={updateConfig.isSuccess ? 'outline' : 'default'}
                  className="min-w-32"
                  size="sm"
                >
                  {updateConfig.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : updateConfig.isSuccess ? (
                    <Check className="h-4 w-4 mr-2 text-green-500" />
                  ) : null}
                  {updateConfig.isPending
                    ? 'Saving...'
                    : updateConfig.isSuccess
                      ? 'Saved'
                      : 'Save Changes'}
                </Button>
              </div>
            </div>
          </CardTitle>
          <CardDescription>
            Update who in the server are admins of the Discord bot
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 mt-4">
          {admins.map((admin) => (
            <div
              key={admin}
              className="flex items-center justify-between p-2 border rounded-md bg-muted/50"
            >
              <code className="text-lg font-mono">{admin}</code>
              <Button
                variant="destructive"
                size="icon"
                onClick={() => handleRemoveAdmin(admin)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {admins.length === 0 && (
            <p className="text-muted-foreground text-sm italic">
              No admins configured.
            </p>
          )}
        </CardContent>
        <CardFooter className="flex flex-col items-start gap-2">
          <div className="flex w-full items-center justify-between gap-2">
            <Input
              type="text"
              value={addAdminId}
              onChange={(e) => setAddAdminId(e.target.value)}
              placeholder="Enter 18-digit User ID"
              className={errors ? 'border-destructive' : ''}
              maxLength={18}
              onKeyDown={(e) => e.key === 'Enter' && handleAddAdmin()}
            />
            <Button
              className="flex items-center gap-2 whitespace-nowrap"
              onClick={handleAddAdmin}
            >
              <Plus className="h-4 w-4" />
              Add Admin
            </Button>
          </div>
          {errors &&
            errors.map((msg, i) => (
              <p key={i} className="text-destructive text-sm font-medium">
                {msg}
              </p>
            ))}
        </CardFooter>
      </Card>
    </div>
  );
}
