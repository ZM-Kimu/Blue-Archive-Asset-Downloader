# GL eliminateRaid Notes

`*eliminateRaid*.zip` files are currently preserved as raw JSON-like `.bytes` payloads during table extraction.

## Current Behavior

- The GL table profile recognizes the archive family.
- Extraction preserves the payload instead of emitting typed semantic JSON.
- CN does not enable GL eliminateRaid semantic routing.
- JP does not consume this archive family.

## Known Facts

- The payload is not `FlatBufferData`.
- The content appears related to ground or raid command scripting.
- No stable typed schema has been added yet.

## Next Step

Add semantic extraction only after the payload format is verified against multiple GL samples and the resulting JSON shape is useful to downstream workflows.
