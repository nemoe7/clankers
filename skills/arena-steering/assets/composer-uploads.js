// Track staged file uploads independently of the composer view.
export function createComposerUploads(store, uploadFile) {
  let nextId = 0;
  const entries = () => store.getState().composerAttachments || [];
  const update = (items) => store.setState({ composerAttachments: items });

  async function upload(id) {
    const item = entries().find((entry) => entry.id === id);
    if (!item) return;
    try {
      const attachment = await uploadFile(item.file);
      if (!attachment) throw new Error("Upload returned no attachment");
      update(entries().map((entry) =>
        entry.id === id ? { ...entry, status: "ready", attachment } : entry));
    } catch (error) {
      console.error(error);
      update(entries().map((entry) =>
        entry.id === id ? { ...entry, status: "failed" } : entry));
    }
  }

  return {
    async stage(files) {
      const added = Array.from(files || [], (file) => ({
        id: String(++nextId), name: file.name, file, status: "uploading",
      }));
      update([...entries(), ...added]);
      await Promise.all(added.map((entry) => upload(entry.id)));
    },
    async retry(id) {
      const item = entries().find((entry) => entry.id === id);
      if (!item || item.status !== "failed") return;
      update(entries().map((entry) =>
        entry.id === id ? { ...entry, status: "uploading" } : entry));
      await upload(id);
    },
    remove(id) {
      update(entries().filter((entry) => entry.id !== id));
    },
    clearSent(ids) {
      const sentIds = new Set(ids);
      update(entries().filter((entry) => !sentIds.has(entry.id)));
    },
  };
}
